from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import Elroy
from ..dependencies import get_elroy
from ..models import (
    ContextRefreshResponse,
    MessageRequest,
    MessageResponse,
    PersonaResponse,
)

router = APIRouter()


@router.post("/", response_model=MessageResponse)
async def send_message(message: MessageRequest, elroy: Elroy = Depends(get_elroy)):
    """
    Send a message to the assistant and get a response.
    """
    try:
        response = elroy.message(input=message.input, enable_tools=message.enable_tools)

        # Optionally refresh context if needed
        elroy.refresh_context_if_needed()

        return MessageResponse(response=response, timestamp=datetime.utcnow())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process message: {str(e)}")


@router.post("/stream")
async def stream_message(message: MessageRequest, elroy: Elroy = Depends(get_elroy)):
    """
    Send a message to the assistant and stream the response.

    This endpoint returns a streaming response using Server-Sent Events (SSE).
    """
    try:
        # This will be handled by FastAPI's StreamingResponse
        # The actual implementation would depend on how you want to handle streaming
        def generate():
            for chunk in elroy.message_stream(input=message.input, enable_tools=message.enable_tools):
                yield f"data: {chunk}\n\n"

            # Optionally refresh context if needed after streaming
            elroy.refresh_context_if_needed()

            yield f"data: [DONE]\n\n"

        from fastapi.responses import StreamingResponse

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process streaming message: {str(e)}")


@router.post("/record", status_code=status.HTTP_204_NO_CONTENT)
async def record_message(role: str, message: str, elroy: Elroy = Depends(get_elroy)):
    """
    Record a message into context without generating a reply.
    """
    try:
        elroy.record_message(role=role, message=message)
        return None
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to record message: {str(e)}")


@router.post("/context/refresh", response_model=ContextRefreshResponse)
async def context_refresh(elroy: Elroy = Depends(get_elroy)):
    """
    Compress context messages and record a memory.
    """
    try:
        elroy.context_refresh()
        return ContextRefreshResponse(refreshed=True, timestamp=datetime.utcnow())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to refresh context: {str(e)}")


@router.get("/context/refresh-if-needed", response_model=ContextRefreshResponse)
async def refresh_context_if_needed(elroy: Elroy = Depends(get_elroy)):
    """
    Check if context refresh is needed and perform it if necessary.
    """
    try:
        refreshed = elroy.refresh_context_if_needed()
        return ContextRefreshResponse(refreshed=refreshed, timestamp=datetime.utcnow())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check context refresh: {str(e)}")


@router.get("/persona", response_model=PersonaResponse)
async def get_persona(elroy: Elroy = Depends(get_elroy)):
    """
    Get the current persona.
    """
    try:
        persona = elroy.get_persona()
        return PersonaResponse(persona=persona)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get persona: {str(e)}")
