from collections.abc import Iterable

from ...core.ctx import ElroyContext
from ...core.services.context_message_service import ContextMessageQueryService
from .data_models import ContextMessage
from .transforms import ContextMessageSetWithMessages


def context_message_query_service(ctx: ElroyContext) -> ContextMessageQueryService:
    return ContextMessageQueryService(ctx.db, ctx.user_id)


def get_or_create_context_message_set(ctx: ElroyContext) -> ContextMessageSetWithMessages:
    return context_message_query_service(ctx).get_or_create_context_message_set()


def get_context_messages(ctx: ElroyContext) -> Iterable[ContextMessage]:
    yield from context_message_query_service(ctx).get_context_messages()


def get_current_system_instruct(ctx: ElroyContext) -> ContextMessage | None:
    return context_message_query_service(ctx).get_current_system_instruct()
