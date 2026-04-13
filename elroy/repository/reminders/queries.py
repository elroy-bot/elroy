from rich.table import Table

from ...core.constants import allow_unused, user_only_tool
from ...core.ctx import ElroyContext
from ...core.services.reminder_service import DueItemLike, ReminderQueryService
from ...core.services.task_service import TaskQueryService
from ...db.db_session import DbSession
from ..context_messages.data_models import ContextMessage


def reminder_query_service(db: DbSession, user_id: int, *, task_queries: TaskQueryService | None = None) -> ReminderQueryService:
    return ReminderQueryService(db, user_id, task_queries=task_queries)


def _reminder_queries(ctx: ElroyContext) -> ReminderQueryService:
    return reminder_query_service(ctx.db, ctx.user_id)


def get_db_due_item_by_name(query_service: ReminderQueryService, name: str) -> DueItemLike | None:
    return query_service.get_db_due_item_by_name(name)


def get_active_due_items(query_service: ReminderQueryService) -> list[DueItemLike]:
    return query_service.get_active_due_items()


def get_due_items(query_service: ReminderQueryService, include_completed: bool = False) -> list[DueItemLike]:
    return query_service.get_due_items(include_completed=include_completed)


def get_active_due_item_names(query_service: ReminderQueryService) -> list[str]:
    return query_service.get_active_due_item_names()


@allow_unused
def get_due_item_by_name(query_service: ReminderQueryService, item_name: str) -> str | None:
    return query_service.get_due_item_by_name(item_name)


def get_due_timed_items(query_service: ReminderQueryService) -> list[DueItemLike]:
    return query_service.get_due_timed_items()


@user_only_tool
def print_active_due_items(ctx: ElroyContext, n: int | None = None) -> str | Table:
    return _reminder_queries(ctx).print_due_items(True, n)


@user_only_tool
def print_inactive_due_items(ctx: ElroyContext, n: int | None = None) -> str | Table:
    return _reminder_queries(ctx).print_due_items(False, n)


def get_due_item_context_msgs(query_service: ReminderQueryService) -> list[ContextMessage]:
    return query_service.get_due_item_context_msgs()
