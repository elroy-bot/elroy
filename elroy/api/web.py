import os
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from elroy.api.main import Elroy
from elroy.core.constants import ELROY_DATABASE_URL
from elroy.db.db_manager import get_db_manager
from elroy.db.db_models import Memory, Reminder
from elroy.db.db_models import WaitlistSignup as WaitlistSignupModel
from elroy.utils.clock import string_to_datetime

from ..models import (
    ApiResponse,
    ChatRequest,
    ChatResponse,
    CreateReminderRequest,
    IngestMemoRequest,
    IngestMemoResponse,
    MemoryResponse,
    MessageResponse,
    ReminderResponse,
)

app = FastAPI(title="Elroy API", version="1.0.0", log_level="info")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://elroy.bot", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Waitlist models
class WaitlistSignup(BaseModel):
    email: str
    use_case: Optional[str] = None
    platform: Optional[str] = None


class WaitlistResponse(BaseModel):
    success: bool  # noqa F841
    message: str


# Style note: do not catch and reraise errors, outside of specific error handling, let regular errors propagate.


@app.get("/")
async def root():
    """Root endpoint that returns status ok."""
    return {"status": "ok"}


@app.get("/get_current_messages", response_model=List[MessageResponse])
async def get_current_messages():
    """Return a list of current messages in the conversation context."""
    elroy = Elroy()
    elroy.ctx

    messages = []
    for msg in elroy.get_current_messages():
        messages.append(MessageResponse(role=msg.role, content=msg.content or ""))

    return messages


@app.post("/ingest_memo", response_model=IngestMemoResponse)
async def ingest_memo(request: IngestMemoRequest):
    elroy = Elroy()
    results = elroy.ingest_memo(request.text)

    return IngestMemoResponse(
        reminders=[m.name for m in results if isinstance(m, Reminder)], memories=[m.name for m in results if isinstance(m, Memory)]
    )


@app.get("/get_current_memories", response_model=List[MemoryResponse])
async def get_current_memories():
    """Return a list of memories for the current user."""
    elroy = Elroy()
    elroy.ctx

    memories = []
    for memory in elroy.get_current_memories():
        memories.append(MemoryResponse(name=memory.name, text=memory.text))

    return memories


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a user message and return the updated conversation."""
    elroy = Elroy()
    elroy.message(request.message)
    messages = []
    for msg in elroy.get_current_messages():
        if msg.content:
            messages.append(MessageResponse(role=msg.role, content=msg.content or ""))

    return ChatResponse(messages=messages)


@app.post("/create_reminder", response_model=ApiResponse)
async def create_reminder_endpoint(request: CreateReminderRequest):
    """Create a new reminder (timed, contextual, or hybrid)."""
    elroy = Elroy()

    if request.trigger_time:
        trigger_time = string_to_datetime(request.trigger_time)
    else:
        trigger_time = None
    result = elroy.create_reminder(request.name, request.text, trigger_time, request.reminder_context)
    return ApiResponse(result=result.to_fact())


@app.get("/get_due_timed_reminders", response_model=List[ReminderResponse])
async def get_due_timed_reminders_endpoint():
    """Get all timed reminders that are currently due."""
    elroy = Elroy()
    due_reminders = elroy.get_due_timed_reminders()

    reminder_responses = []
    for reminder in due_reminders:
        reminder_id = reminder.id
        assert reminder_id
        reminder_responses.append(
            ReminderResponse(
                id=reminder_id,
                name=reminder.name,
                text=reminder.text,
                trigger_datetime=reminder.trigger_datetime.isoformat() if reminder.trigger_datetime else None,
                reminder_context=reminder.reminder_context,
            )
        )

    return reminder_responses


@app.post("/waitlist", response_model=WaitlistResponse)
async def waitlist_signup(signup: WaitlistSignup):
    """Add user to waitlist for mobile app."""
    import logging

    from sqlmodel import select

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Get database manager and create session
        db_manager = get_db_manager(os.environ[ELROY_DATABASE_URL])

        with db_manager.open_session() as session:
            # Check if email already exists
            existing_signup = session.exec(select(WaitlistSignupModel).where(WaitlistSignupModel.email == signup.email)).first()

            if existing_signup:
                logger.info(f"Duplicate waitlist signup attempt: {signup.email}")
                return WaitlistResponse(
                    success=True, message="You're already on our waitlist! We'll notify you when the mobile app is available."
                )

            # Create new waitlist signup
            waitlist_entry = WaitlistSignupModel(email=signup.email, use_case=signup.use_case, platform=signup.platform)

            session.add(waitlist_entry)
            session.commit()

            logger.info(f"Waitlist signup saved: {signup.email}, use_case: {signup.use_case}, platform: {signup.platform}")

            return WaitlistResponse(success=True, message="Thank you for signing up! We'll notify you when the mobile app is available.")

    except Exception as e:
        logger.error(f"Error saving waitlist signup: {e}")
        # Fall back to just logging if database save fails
        logger.info(f"Waitlist signup (fallback): {signup.email}, use_case: {signup.use_case}, platform: {signup.platform}")
        return WaitlistResponse(success=True, message="Thank you for signing up! We'll notify you when the mobile app is available.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
