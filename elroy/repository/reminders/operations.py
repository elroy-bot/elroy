from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from ...core.constants import RecoverableToolError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...utils.clock import utc_now
from ...utils.utils import is_blank
from .queries import get_active_due_item_names, get_db_due_item_by_name

logger = get_logger()


class DueItemAlreadyExistsError(RecoverableToolError):
    def __init__(self, item_name: str, item_type: str):
        super().__init__(f"{item_type} due item '{item_name}' already exists")


@dataclass(frozen=True)
class ReminderOperationCallbacks:
    create_task_fn: Callable[..., object]
    complete_task_fn: Callable[[str, str | None], object]
    delete_task_fn: Callable[[str, str | None], object]


class ReminderOrchestrator:
    def __init__(self, ctx: ElroyContext, callbacks: ReminderOperationCallbacks):
        self.ctx = ctx
        self.callbacks = callbacks

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

        if get_db_due_item_by_name(self.ctx, name):
            item_type = "Timed" if trigger_time else "Contextual"
            raise DueItemAlreadyExistsError(name, item_type)

        try:
            return self.callbacks.create_task_fn(
                name,
                text,
                trigger_datetime=trigger_time,
                trigger_context=trigger_context,
            )
        except Exception as e:
            from ..tasks.operations import TaskAlreadyExistsError

            if isinstance(e, TaskAlreadyExistsError):
                item_type = "Timed" if trigger_time else "Contextual"
                raise DueItemAlreadyExistsError(name, item_type) from e
            raise

    def do_complete_due_item(self, item_name: str, closing_comment: str | None = None) -> str:
        due_item = get_db_due_item_by_name(self.ctx, item_name)
        if not due_item:
            active_names = get_active_due_item_names(self.ctx)
            raise RecoverableToolError(f"Active due item '{item_name}' not found. Active due items: {', '.join(active_names)}")

        logger.info(f"Completing agenda-backed due item {item_name} for user {self.ctx.user_id}")
        self.callbacks.complete_task_fn(item_name, closing_comment)

        if closing_comment:
            return f"Due item '{item_name}' has been marked as completed. Comment: {closing_comment}"
        return f"Due item '{item_name}' has been marked as completed."

    def do_delete_due_item(self, item_name: str, closing_comment: str | None = None) -> str:
        due_item = get_db_due_item_by_name(self.ctx, item_name)
        if not due_item:
            active_names = get_active_due_item_names(self.ctx)
            raise RecoverableToolError(f"Active due item '{item_name}' not found. Active due items: {', '.join(active_names)}")

        logger.info(f"Deleting agenda-backed due item {item_name} for user {self.ctx.user_id}")
        self.callbacks.delete_task_fn(item_name, closing_comment)

        if closing_comment:
            return f"Due item '{item_name}' has been deleted. Comment: {closing_comment}"
        return f"Due item '{item_name}' has been deleted."


def _orchestrator(ctx: ElroyContext) -> ReminderOrchestrator:
    from ..tasks.operations import complete_task, create_task, delete_task

    return ReminderOrchestrator(
        ctx=ctx,
        callbacks=ReminderOperationCallbacks(
            create_task_fn=lambda name, text, **kwargs: create_task(ctx, name, text, **kwargs),
            complete_task_fn=lambda item_name, closing_comment: complete_task(ctx, item_name, closing_comment),
            delete_task_fn=lambda item_name, closing_comment: delete_task(ctx, item_name, closing_comment),
        ),
    )


def create_onboarding_due_item(ctx: ElroyContext, preferred_name: str) -> None:
    _orchestrator(ctx).create_onboarding_due_item(preferred_name)


def do_create_due_item(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time: datetime | None = None,
    trigger_context: str | None = None,
):
    return _orchestrator(ctx).do_create_due_item(name, text, trigger_time, trigger_context)


def do_complete_due_item(ctx: ElroyContext, item_name: str, closing_comment: str | None = None) -> str:
    return _orchestrator(ctx).do_complete_due_item(item_name, closing_comment)


def do_delete_due_item(ctx: ElroyContext, item_name: str, closing_comment: str | None = None) -> str:
    return _orchestrator(ctx).do_delete_due_item(item_name, closing_comment)
