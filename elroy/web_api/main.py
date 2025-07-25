import os
import tempfile
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from litellm import transcription
from pydantic import BaseModel

from elroy.api import Elroy
from elroy.repository.memories.models import MemoryResponse

app = FastAPI(title="Elroy API", version="1.0.0")

# Style note: do not catch and reraise errors, outside of specific error handling, let regular errors propagate.


class MessageResponse(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    messages: List[MessageResponse]


@app.get("/get_current_messages", response_model=List[MessageResponse])
async def get_current_messages():
    """Return a list of current messages in the conversation context."""
    elroy = Elroy()
    elroy.ctx

    messages = []
    for msg in elroy.get_current_messages():
        messages.append(MessageResponse(role=msg.role, content=msg.content or ""))

    return messages


@app.post("/create_augmented_memory", response_model=MemoryResponse)
async def create_augmented_memory():
    elroy = Elroy()

    text = "TODO"

    return elroy.create_augmented_memory(text)


@app.get("/get_current_memories", response_model=List[MemoryResponse])
async def get_current_memories():
    """Return a list of memories for the current user."""
    elroy = Elroy()
    elroy.ctx

    memories = []
    for memory in elroy.get_current_memories():
        memories.append(MemoryResponse(title=memory.name, text=memory.text))

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


@app.post("/create_voice_memory", response_model=str)
async def create_voice_memory(file: UploadFile = File(...)):
    """Accept a voice recording upload, transcribe it, and create a memory."""
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")

    try:
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Transcribe the audio using litellm
            with open(temp_file_path, "rb") as audio_file:
                response = transcription(model="whisper-1", file=audio_file)

            # Extract the transcribed text
            transcribed_text = response.text if hasattr(response, "text") else str(response)

            # Create memory using Elroy
            elroy = Elroy()
            # Use the original filename as the memory name, or generate one based on timestamp
            memory_name = f"Voice memo: {file.filename or 'untitled'}"
            result = elroy.create_memory(memory_name, transcribed_text)

            return result

        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing voice memo: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
