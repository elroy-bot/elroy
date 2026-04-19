from ...core.ctx import ElroyContext
from ..recall.factory import build_recall_context_bridge, build_recall_indexer
from .store import TaskStore
from .task_mutation_orchestrator import TaskMutationOrchestrator


def build_task_store(ctx: ElroyContext) -> TaskStore:
    return TaskStore(ctx.db, ctx.user_id)


def build_task_mutation_orchestrator(ctx: ElroyContext) -> TaskMutationOrchestrator:
    return TaskMutationOrchestrator(
        store=build_task_store(ctx),
        recall_indexer=build_recall_indexer(ctx),
        recall_context_bridge=build_recall_context_bridge(ctx),
    )
