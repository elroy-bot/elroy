import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from elroy.api.main import Elroy
from elroy.core.constants import ELROY_DATABASE_URL, TOOL
from elroy.db.db_manager import get_db_manager
from elroy.db.db_models import Memory, Reminder
from elroy.db.db_models import WaitlistSignup as WaitlistSignupModel
from elroy.utils.clock import string_to_datetime

from ..models import (
    ApiResponse,
    ChatRequest,
    ChatResponse,
    CompleteReminderRequest,
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
    CORSMiddleware,  # type: ignore
    allow_origins=["https://elroy.bot", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Waitlist models
class WaitlistSignup(BaseModel):
    email: str
    use_case: str | None = None
    platform: str | None = None


class WaitlistResponse(BaseModel):
    success: bool  # noqa F841
    message: str


# Style note: do not catch and reraise errors, outside of specific error handling, let regular errors propagate.


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that returns 500 JSON response instead of HTML."""
    return JSONResponse(status_code=500, content={"error": "Internal server error", "message": str(exc)})


@app.get("/")
async def root():
    """Root endpoint that returns status ok."""
    return {"status": "ok"}


@app.get("/get_current_messages", response_model=list[MessageResponse])
async def get_current_messages():
    """Return a list of current messages in the conversation context."""
    elroy = Elroy()
    _ = elroy.ctx

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


@app.get("/get_current_memories", response_model=list[MemoryResponse])
async def get_current_memories():
    """Return a list of memories for the current user."""
    elroy = Elroy()
    _ = elroy.ctx

    memories = []
    for memory in elroy.get_current_memories():
        memories.append(MemoryResponse(name=memory.name, text=memory.text))

    return memories


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a user message and return the updated conversation."""
    elroy = Elroy(show_internal_thought=False, show_tool_calls=False)
    elroy.message(input=request.message)
    messages = []
    for msg in elroy.get_current_messages():
        if msg.content and msg.role != TOOL:
            messages.append(MessageResponse(role=msg.role, content=msg.content or ""))

    return ChatResponse(messages=messages)


@app.post("/create_reminder", response_model=ApiResponse)
async def create_reminder_endpoint(request: CreateReminderRequest):
    """Create a new reminder (timed, contextual, or hybrid)."""
    elroy = Elroy()

    trigger_time = string_to_datetime(request.trigger_time) if request.trigger_time else None
    result = elroy.create_reminder(request.name, request.text, trigger_time, request.reminder_context)
    return ApiResponse(result=result.to_fact())


@app.post("/mark_reminder_completed", response_model=ApiResponse)
async def mark_reminder_completed_endpoint(request: CompleteReminderRequest):
    """Mark a reminder as completed."""
    elroy = Elroy()
    result = elroy.complete_reminder(request.name, request.closing_comment)
    return ApiResponse(result=result)


@app.get("/get_reminders", response_model=list[ReminderResponse])
async def get_reminders_endpoint(include_completed: bool = False):
    """Get reminders, optionally including completed ones."""
    elroy = Elroy()
    reminders = elroy.get_reminders(include_completed=include_completed)

    reminder_responses = []
    for reminder in reminders:
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
