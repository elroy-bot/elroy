from dataclasses import dataclass
from datetime import timedelta

from ...llm.client import LlmClient
from ...tools.registry import ToolRegistry
from .session import ContextMessageSession


@dataclass(frozen=True)
class ContextRefreshRuntime:
    tool_registry: ToolRegistry
    chat_model_inline_tool_calls: bool
    fast_llm: LlmClient
    chat_model_name: str
    max_tokens: int
    context_refresh_target_tokens: int
    max_in_context_message_age: timedelta
    messages_between_memory: int


@dataclass(frozen=True)
class ContextValidationRuntime:
    ensure_alternating_roles: bool


def build_context_refresh_runtime(context_session: ContextMessageSession) -> ContextRefreshRuntime:
    config = context_session.turn.config
    return ContextRefreshRuntime(
        tool_registry=config.tool_registry,
        chat_model_inline_tool_calls=config.chat_model.inline_tool_calls,
        fast_llm=config.fast_llm,
        chat_model_name=config.chat_model.name,
        max_tokens=config.max_tokens,
        context_refresh_target_tokens=config.context_refresh_target_tokens,
        max_in_context_message_age=config.max_in_context_message_age,
        messages_between_memory=config.messages_between_memory,
    )


def build_context_validation_runtime(context_session: ContextMessageSession) -> ContextValidationRuntime:
    return ContextValidationRuntime(
        ensure_alternating_roles=context_session.turn.config.chat_model.ensure_alternating_roles,
    )
