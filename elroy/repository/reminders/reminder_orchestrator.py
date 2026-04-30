from collections.abc import Callable
from datetime import datetime

from ...core.constants import RecoverableToolError
from ...core.logging import get_logger
from ...core.turn import TurnContext
from ...utils.clock import utc_now
from ...utils.utils import is_blank
from ..tasks.store import TaskAlreadyExistsError
from ..user.session import build_user_session
from .queries import do_get_active_due_item_names, do_get_db_due_item_by_name

logger = get_logger()


class DueItemAlreadyExistsError(RecoverableToolError):
    def __init__(self, item_name: str, item_type: str):
        super().__init__(f"{item_type} due item '{item_name}' already exists")


class ReminderOrchestrator:
    def __init__(
        self,
        turn: TurnContext,
        create_task_fn: Callable[..., object],
        complete_task_fn: Callable[[str, str | None], object],
        delete_task_fn: Callable[[str, str | None], object],
    ):
        self.turn = turn
        self.create_task_fn = create_task_fn
        self.complete_task_fn = complete_task_fn
        self.delete_task_fn = delete_task_fn

    def create_onboarding_due_item(self, preferred_name: str) -> None:
        self.do_create_due_item(
            name=f"Introduce myself to {preferred_name}",
            text="Introduce myself - a few things that make me unique are my ability to form long term memories, and the ability to create due items that surface at the right time or context",
            trigger_context="When user logs in for the first time",
        )

    def do_create_due_item(
        self,
        name: str,
        text: str,
        trigger_time: datetime | None = None,
        trigger_context: str | None = None,
    ):
        if is_blank(name):
            raise ValueError("Due item name cannot be empty")
        if not trigger_time and not trigger_context:
            raise RecoverableToolError("Either trigger_time or trigger_context must be provided for due items")
        if trigger_time and trigger_time < utc_now():
            raise RecoverableToolError(
                f"Attempted to create a due item for {trigger_time}, which is in the past. The current time is {utc_now()}"
            )

        if do_get_db_due_item_by_name(self.turn, name):
            item_type = "Timed" if trigger_time else "Contextual"
            raise DueItemAlreadyExistsError(name, item_type)

        try:
            return self.create_task_fn(
                name,
                text,
                trigger_datetime=trigger_time,
                trigger_context=trigger_context,
            )
        except Exception as e:
            if isinstance(e, TaskAlreadyExistsError):
                item_type = "Timed" if trigger_time else "Contextual"
                raise DueItemAlreadyExistsError(name, item_type) from e
            raise

    def do_complete_due_item(self, item_name: str, closing_comment: str | None = None) -> str:
        due_item = do_get_db_due_item_by_name(self.turn, item_name)
        if not due_item:
            active_names = do_get_active_due_item_names(self.turn)
            raise RecoverableToolError(f"Active due item '{item_name}' not found. Active due items: {', '.join(active_names)}")

        logger.info(f"Completing agenda-backed due item {item_name} for user {build_user_session(self.turn).user_id}")
        self.complete_task_fn(item_name, closing_comment)

        if closing_comment:
            return f"Due item '{item_name}' has been marked as completed. Comment: {closing_comment}"
        return f"Due item '{item_name}' has been marked as completed."

    def do_delete_due_item(self, item_name: str, closing_comment: str | None = None) -> str:
        due_item = do_get_db_due_item_by_name(self.turn, item_name)
        if not due_item:
            active_names = do_get_active_due_item_names(self.turn)
            raise RecoverableToolError(f"Active due item '{item_name}' not found. Active due items: {', '.join(active_names)}")

        logger.info(f"Deleting agenda-backed due item {item_name} for user {build_user_session(self.turn).user_id}")
        self.delete_task_fn(item_name, closing_comment)

        if closing_comment:
            return f"Due item '{item_name}' has been deleted. Comment: {closing_comment}"
        return f"Due item '{item_name}' has been deleted."
