from ...core.turn import TurnContext
from ..recall.factory import build_recall_context_bridge, build_recall_indexer
from ..user.session import build_user_session
from .store import TaskStore
from .task_mutation_orchestrator import TaskMutationOrchestrator


def build_task_store(turn: TurnContext) -> TaskStore:
    user_session = build_user_session(turn)
    return TaskStore(user_session.db, user_session.user_id)


def build_task_mutation_orchestrator(turn: TurnContext) -> TaskMutationOrchestrator:
    return TaskMutationOrchestrator(
        store=build_task_store(turn),
        recall_indexer=build_recall_indexer(turn),
        recall_context_bridge=build_recall_context_bridge(turn),
    )
