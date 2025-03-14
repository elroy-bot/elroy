from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import Elroy
from ..dependencies import get_elroy
from ..models import GoalComplete, GoalCreate, GoalStatusUpdate

router = APIRouter()


@router.post("/", response_model=str, status_code=status.HTTP_201_CREATED)
async def create_goal(goal: GoalCreate, elroy: Elroy = Depends(get_elroy)):
    """
    Create a new goal.
    """
    try:
        result = elroy.create_goal(
            goal_name=goal.goal_name,
            strategy=goal.strategy,
            description=goal.description,
            end_condition=goal.end_condition,
            time_to_completion=goal.time_to_completion,
            priority=goal.priority,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create goal: {str(e)}")


@router.post("/{goal_name}/status", response_model=str)
async def add_goal_status_update(goal_name: str, status_update: GoalStatusUpdate, elroy: Elroy = Depends(get_elroy)):
    """
    Add a status update to a goal.
    """
    try:
        result = elroy.add_goal_status_update(goal_name=goal_name, status_update_or_note=status_update.status_update_or_note)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add status update: {str(e)}")


@router.post("/{goal_name}/complete", response_model=str)
async def mark_goal_completed(goal_name: str, goal_complete: GoalComplete, elroy: Elroy = Depends(get_elroy)):
    """
    Mark a goal as completed.
    """
    try:
        result = elroy.mark_goal_completed(goal_name=goal_name, closing_comments=goal_complete.closing_comments)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to mark goal as completed: {str(e)}")


@router.get("/", response_model=List[str])
async def get_active_goal_names(elroy: Elroy = Depends(get_elroy)):
    """
    Get the list of names for all active goals.
    """
    try:
        return elroy.get_active_goal_names()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get active goal names: {str(e)}")


@router.get("/{goal_name}", response_model=Optional[str])
async def get_goal_by_name(goal_name: str, elroy: Elroy = Depends(get_elroy)):
    """
    Get a goal by name.
    """
    try:
        result = elroy.get_goal_by_name(goal_name)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Goal '{goal_name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get goal: {str(e)}")
