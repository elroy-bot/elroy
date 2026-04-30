from ...core.turn import TurnContext
from ..context_messages.factory import build_context_message_read_store, build_context_refresh_orchestrator
from ..context_messages.session import build_context_message_session
from ..user.session import build_user_session
from .context_bridge import RecallContextBridge
from .indexer import RecallIndexer
from .runtime import build_recall_runtime


def build_recall_indexer(turn: TurnContext) -> RecallIndexer:
    user_session = build_user_session(turn)
    runtime = build_recall_runtime(turn)
    return RecallIndexer(
        db=user_session.db,
        user_id=user_session.user_id,
        llm=runtime.llm,
    )


def build_recall_context_bridge(turn: TurnContext) -> RecallContextBridge:
    context_session = build_context_message_session(turn)
    context_refresh_orchestrator = build_context_refresh_orchestrator(context_session)
    context_message_read_store = build_context_message_read_store(context_session)
    user_session = build_user_session(turn)
    return RecallContextBridge(
        db=user_session.db,
        user_id=user_session.user_id,
        get_context_messages_fn=context_message_read_store.get_context_messages,
        add_context_messages_fn=context_refresh_orchestrator.add_context_messages,
        remove_context_messages_fn=context_refresh_orchestrator.store.remove_context_messages,
    )
