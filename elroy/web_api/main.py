from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from elroy.api import Elroy

app = FastAPI(title="Elroy API", version="1.0.0")


class MessageResponse(BaseModel):
    role: str
    content: str


class MemoryResponse(BaseModel):
    title: str
    text: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    messages: List[MessageResponse]


@app.get("/get_current_messages", response_model=List[MessageResponse])
async def get_current_messages():
    """Return a list of current messages in the conversation context."""
    try:
        elroy = Elroy()
        elroy.ctx

        messages = []
        for msg in elroy.get_current_messages():
            messages.append(MessageResponse(role=msg.role, content=msg.content or ""))

        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_current_memories", response_model=List[MemoryResponse])
async def get_current_memories():
    """Return a list of memories for the current user."""
    try:
        elroy = Elroy()
        elroy.ctx

        memories = []
        for memory in elroy.get_current_memories():
            memories.append(MemoryResponse(title=memory.name, text=memory.text))

        return memories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a user message and return the updated conversation."""
    try:
        elroy = Elroy()
        elroy.message(request.message)
        messages = []
        for msg in elroy.get_current_messages():
            if msg.content:
                messages.append(MessageResponse(role=msg.role, content=msg.content or ""))

        return ChatResponse(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
