from fastapi import APIRouter, Depends, HTTPException, status

from ...api import Elroy
from ..dependencies import get_elroy
from ..models import MemoryCreate, MemoryQuery

router = APIRouter()


@router.post("/", response_model=str, status_code=status.HTTP_201_CREATED)
async def create_memory(memory: MemoryCreate, elroy: Elroy = Depends(get_elroy)):
    """
    Create a new memory.
    """
    try:
        result = elroy.create_memory(name=memory.name, text=memory.text)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create memory: {str(e)}")


@router.post("/query", response_model=str)
async def query_memory(query: MemoryQuery, elroy: Elroy = Depends(get_elroy)):
    """
    Query memories using semantic search.
    """
    try:
        result = elroy.query_memory(query.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to query memories: {str(e)}")


@router.post("/remember", response_model=str, status_code=status.HTTP_201_CREATED)
async def remember(memory: MemoryCreate, elroy: Elroy = Depends(get_elroy)):
    """
    Alias for create_memory.
    """
    try:
        result = elroy.remember(name=memory.name, text=memory.text)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create memory: {str(e)}")
