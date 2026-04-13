from rich.table import Table

from ...core.constants import allow_unused, user_only_tool
from ...core.ctx import ElroyContext
from ...core.services.reminder_service import DueItemLike, ReminderQueryService
from ..context_messages.data_models import ContextMessage


def _reminder_queries(ctx: ElroyContext) -> ReminderQueryService:
    return ReminderQueryService(ctx.db, ctx.user_id)


def get_db_due_item_by_name(ctx: ElroyContext, name: str) -> DueItemLike | None:
    return _reminder_queries(ctx).get_db_due_item_by_name(name)


def get_active_due_items(ctx: ElroyContext) -> list[DueItemLike]:
    return _reminder_queries(ctx).get_active_due_items()


def get_due_items(ctx: ElroyContext, include_completed: bool = False) -> list[DueItemLike]:
    return _reminder_queries(ctx).get_due_items(include_completed=include_completed)


def get_active_due_item_names(ctx: ElroyContext) -> list[str]:
    return _reminder_queries(ctx).get_active_due_item_names()


def get_due_timed_items(ctx: ElroyContext) -> list[DueItemLike]:
    return _reminder_queries(ctx).get_due_timed_items()


@allow_unused
def get_due_item_by_name(ctx: ElroyContext, item_name: str) -> str | None:
    return _reminder_queries(ctx).get_due_item_by_name(item_name)


@user_only_tool
def print_active_due_items(ctx: ElroyContext, n: int | None = None) -> str | Table:
    return _reminder_queries(ctx).print_due_items(True, n)


@user_only_tool
def print_inactive_due_items(ctx: ElroyContext, n: int | None = None) -> str | Table:
    return _reminder_queries(ctx).print_due_items(False, n)


def get_due_item_context_msgs(ctx: ElroyContext) -> list[ContextMessage]:
    return _reminder_queries(ctx).get_due_item_context_msgs()
