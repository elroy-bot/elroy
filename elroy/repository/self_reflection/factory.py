from ...core.turn import TurnContext
from ..context_messages.factory import build_context_message_read_store
from ..context_messages.session import build_context_message_session
from .orchestrator import SelfReflectionConfig, SelfReflectionOrchestrator


def build_self_reflection_orchestrator(turn: TurnContext) -> SelfReflectionOrchestrator:
    return SelfReflectionOrchestrator(
        config=SelfReflectionConfig(
            messages_between_self_reflection=turn.config.messages_between_self_reflection,
        )
    )


def reflect_from_current_context(turn: TurnContext) -> None:
    context_messages = list(build_context_message_read_store(build_context_message_session(turn)).get_context_messages())
    build_self_reflection_orchestrator(turn).run(context_messages)
