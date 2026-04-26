from ...core.async_tasks import schedule_task
from ...core.ctx import ElroyContext
from ...core.db import require_db_session
from ..user.queries import do_get_user_preferred_name, get_assistant_name, get_persona
from .context_refresh_orchestrator import (
    ContextRefreshConfig,
    ContextRefreshDependencies,
    ContextRefreshOrchestrator,
)
from .queries import ContextMessageReadStore
from .store import ContextMessageStore
from .system_prompt_builder import SystemPromptBuilder, SystemPromptMetadataProviders


def build_context_message_read_store(ctx: ElroyContext) -> ContextMessageReadStore:
    return ContextMessageReadStore(require_db_session(ctx), ctx.user_id)


def build_context_message_store(ctx: ElroyContext) -> ContextMessageStore:
    return ContextMessageStore(build_context_message_read_store(ctx))


def build_system_prompt_builder(ctx: ElroyContext) -> SystemPromptBuilder:
    return SystemPromptBuilder(
        tool_registry=ctx.tool_registry,
        chat_model_inline_tool_calls=ctx.chat_model.inline_tool_calls,
        metadata_providers=SystemPromptMetadataProviders(
            get_persona_fn=lambda: get_persona(ctx),
        ),
    )


def build_context_refresh_orchestrator(ctx: ElroyContext) -> ContextRefreshOrchestrator:
    from ..memories.factory import (
        create_mem_from_current_context,
        formulate_memory,
        get_or_create_memory_op_tracker,
    )

    def create_memory_from_tool(name: str, text: str) -> str:
        from ..memories.tools import create_memory

        return create_memory(ctx, name, text)

    return ContextRefreshOrchestrator(
        read_store=build_context_message_read_store(ctx),
        store=build_context_message_store(ctx),
        system_prompt_builder=build_system_prompt_builder(ctx),
        fast_llm=ctx.fast_llm,
        config=ContextRefreshConfig(
            chat_model_name=ctx.chat_model.name,
            max_tokens=ctx.max_tokens,
            context_refresh_target_tokens=ctx.context_refresh_target_tokens,
            max_in_context_message_age=ctx.max_in_context_message_age,
            messages_between_memory=ctx.messages_between_memory,
        ),
        dependencies=ContextRefreshDependencies(
            get_assistant_name_fn=lambda: get_assistant_name(ctx),
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(require_db_session(ctx).session, ctx.user_id),
            get_or_create_memory_op_tracker_fn=lambda: get_or_create_memory_op_tracker(ctx),
            schedule_memory_creation_fn=lambda: schedule_task(create_mem_from_current_context, ctx),
            formulate_memory_fn=lambda context_messages: formulate_memory(ctx, context_messages),
            create_memory_fn=create_memory_from_tool,
        ),
    )
