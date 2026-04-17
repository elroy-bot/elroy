from collections.abc import Iterable, Iterator

from ...core.async_tasks import schedule_task
from ...core.constants import user_only_tool
from ...core.ctx import ElroyContext
from ..memories.operations import (
    create_mem_from_current_context,
    formulate_memory,
    get_or_create_memory_op_tracker,
)
from ..memories.tools import create_memory
from ..user.queries import do_get_user_preferred_name, get_assistant_name, get_persona
from .context_refresh_orchestrator import (
    ContextRefreshConfig,
    ContextRefreshMemoryCallbacks,
    ContextRefreshMetadataProviders,
    ContextRefreshOrchestrator,
)
from .data_models import ContextMessage
from .queries import ContextMessageQueryService
from .store import ContextMessageStore
from .system_prompt_builder import SystemPromptBuilder, SystemPromptMetadataProviders


def _store(ctx: ElroyContext) -> ContextMessageStore:
    query_service = ContextMessageQueryService(ctx.db, ctx.user_id)
    return ContextMessageStore(query_service)


def _orchestrator(ctx: ElroyContext) -> ContextRefreshOrchestrator:
    query_service = ContextMessageQueryService(ctx.db, ctx.user_id)
    store = ContextMessageStore(query_service)
    system_prompt_builder = SystemPromptBuilder(
        tool_registry=ctx.tool_registry,
        chat_model_inline_tool_calls=ctx.chat_model.inline_tool_calls,
        metadata_providers=SystemPromptMetadataProviders(
            get_persona_fn=lambda: get_persona(ctx),
        ),
    )
    return ContextRefreshOrchestrator(
        query_service=query_service,
        store=store,
        system_prompt_builder=system_prompt_builder,
        fast_llm=ctx.fast_llm,
        config=ContextRefreshConfig(
            chat_model_name=ctx.chat_model.name,
            max_tokens=ctx.max_tokens,
            context_refresh_target_tokens=ctx.context_refresh_target_tokens,
            max_in_context_message_age=ctx.max_in_context_message_age,
            messages_between_memory=ctx.messages_between_memory,
        ),
        metadata_providers=ContextRefreshMetadataProviders(
            get_assistant_name_fn=lambda: get_assistant_name(ctx),
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(ctx.db.session, ctx.user_id),
        ),
        memory_callbacks=ContextRefreshMemoryCallbacks(
            get_or_create_memory_op_tracker_fn=lambda: get_or_create_memory_op_tracker(ctx),
            schedule_memory_creation_fn=lambda: schedule_task(create_mem_from_current_context, ctx),
            formulate_memory_fn=lambda context_messages: formulate_memory(ctx, context_messages),
            create_memory_fn=lambda name, text: create_memory(ctx, name, text),
        ),
    )


def persist_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> Iterator[int]:
    return _store(ctx).persist_messages(messages)


def replace_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    _store(ctx).replace_context_messages(messages)


def remove_context_messages(ctx: ElroyContext, messages: list[ContextMessage]) -> None:
    _store(ctx).remove_context_messages(messages)


def add_context_message(ctx: ElroyContext, message: ContextMessage) -> None:
    _orchestrator(ctx).add_context_message(message)


def add_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    _orchestrator(ctx).add_context_messages(messages)


def get_refreshed_system_message(ctx: ElroyContext) -> ContextMessage:
    return _orchestrator(ctx).get_refreshed_system_message()


def context_refresh(ctx: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    _orchestrator(ctx).context_refresh(context_messages)


def drop_old_context_messages(ctx: ElroyContext) -> None:
    _orchestrator(ctx).drop_old_context_messages()


def refresh_context_if_needed(ctx: ElroyContext):
    _orchestrator(ctx).refresh_context_if_needed()


@user_only_tool
def save(ctx: ElroyContext, n: int = 1000) -> str:
    """
    Saves the last n message from context.
    """
    return _orchestrator(ctx).save(n)


@user_only_tool
def pop(ctx: ElroyContext, n: int) -> str:
    """
    Removes the last n messages from the context

    Args:
        n (int): The number of messages to remove

    Returns:
       str: The result of the pop operation.
    """
    return _orchestrator(ctx).pop(n)


@user_only_tool
def rewrite(ctx: ElroyContext, new_message: str) -> str:
    """
    Replaces the last message assistant in the context with the new message
        new_message (str): The new message to replace the last message with

    Returns:
        str: The result of the rewrite operation
    """
    return _orchestrator(ctx).rewrite(new_message)


@user_only_tool
def refresh_system_instructions(ctx: ElroyContext) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """
    return _orchestrator(ctx).refresh_system_instructions()


@user_only_tool
def reset_messages(ctx: ElroyContext) -> str:
    """Resets the context for the user, removing all messages from the context except the system message.
    This should be used sparingly, only at the direct request of the user.

    Args:
        user_id (int): user id

    Returns:
        str: The result of the context reset
    """
    return _orchestrator(ctx).reset_messages()
