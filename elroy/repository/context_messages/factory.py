from ...core.async_tasks import schedule_task
from ..user.queries import do_get_user_preferred_name, get_assistant_name, get_persona
from .context_refresh_orchestrator import (
    ContextRefreshConfig,
    ContextRefreshDependencies,
    ContextRefreshOrchestrator,
)
from .queries import ContextMessageReadStore
from .runtime import build_context_refresh_runtime
from .session import ContextMessageSession
from .store import ContextMessageStore
from .system_prompt_builder import SystemPromptBuilder, SystemPromptMetadataProviders


def build_context_message_read_store(context_session: ContextMessageSession) -> ContextMessageReadStore:
    return ContextMessageReadStore(context_session.db, context_session.user_id)


def build_context_message_store(context_session: ContextMessageSession) -> ContextMessageStore:
    return ContextMessageStore(build_context_message_read_store(context_session))


def build_system_prompt_builder(context_session: ContextMessageSession) -> SystemPromptBuilder:
    runtime = build_context_refresh_runtime(context_session)
    return SystemPromptBuilder(
        tool_registry=runtime.tool_registry,
        chat_model_inline_tool_calls=runtime.chat_model_inline_tool_calls,
        metadata_providers=SystemPromptMetadataProviders(
            get_persona_fn=lambda: get_persona(context_session.user_session, context_session.user_runtime),
        ),
    )


def build_context_refresh_orchestrator(context_session: ContextMessageSession) -> ContextRefreshOrchestrator:
    from ..memories.factory import (
        create_mem_from_current_context,
        formulate_memory,
        get_or_create_memory_op_tracker,
    )
    from ..memories.tools import do_create_memory
    from ..self_reflection.factory import reflect_from_current_context

    runtime = build_context_refresh_runtime(context_session)

    return ContextRefreshOrchestrator(
        read_store=build_context_message_read_store(context_session),
        store=build_context_message_store(context_session),
        system_prompt_builder=build_system_prompt_builder(context_session),
        fast_llm=runtime.fast_llm,
        config=ContextRefreshConfig(
            chat_model_name=runtime.chat_model_name,
            max_tokens=runtime.max_tokens,
            context_refresh_target_tokens=runtime.context_refresh_target_tokens,
            max_in_context_message_age=runtime.max_in_context_message_age,
            messages_between_memory=runtime.messages_between_memory,
            messages_between_self_reflection=runtime.messages_between_self_reflection,
        ),
        dependencies=ContextRefreshDependencies(
            get_assistant_name_fn=lambda: get_assistant_name(context_session.user_session, context_session.user_runtime),
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(
                context_session.user_session.db.session,
                context_session.user_session.user_id,
            ),
            get_or_create_memory_op_tracker_fn=lambda: get_or_create_memory_op_tracker(context_session.turn),
            schedule_memory_creation_fn=lambda: schedule_task(create_mem_from_current_context, context_session.turn),
            schedule_self_reflection_fn=lambda: schedule_task(reflect_from_current_context, context_session.turn),
            formulate_memory_fn=lambda context_messages: formulate_memory(context_session.turn, context_messages),
            create_memory_fn=lambda name, text: do_create_memory(context_session.turn, name, text),
        ),
    )
