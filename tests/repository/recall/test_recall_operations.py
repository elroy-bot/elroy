from sqlmodel import select

from elroy.core.session import open_turn_context
from elroy.db.db_models import Memory
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.memories.factory import build_memory_lifecycle_orchestrator
from elroy.repository.recall.factory import build_recall_context_bridge
from elroy.repository.recall.queries import is_in_context_message
from elroy.repository.user.session import build_user_session


def test_add_to_current_context_by_name_scopes_to_current_user(ctx, db_manager, chat_model_name, tmp_path):
    with open_turn_context(ctx) as turn:
        build_memory_lifecycle_orchestrator(turn).do_create_memory("Shared Memory Name", "Current user memory", [], False)

    other_ctx = ctx.init(
        user_token="other-user-token",
        database_url=db_manager.url,
        chat_model=chat_model_name,
        use_background_threads=True,
        memory_dir=str(tmp_path / "other-memories"),
    )
    other_ctx.__dict__["llm"] = ctx.llm
    other_ctx.__dict__["fast_llm"] = ctx.fast_llm

    with open_turn_context(other_ctx) as turn:
        other_memory = build_memory_lifecycle_orchestrator(turn).do_create_memory("Shared Memory Name", "Other user memory", [], False)
        assert other_memory.id is not None

    with open_turn_context(ctx) as turn:
        build_recall_context_bridge(turn).add_to_current_context_by_name("Shared Memory Name", Memory)

    context_messages = list(get_context_messages(ctx))
    with open_turn_context(other_ctx) as turn:
        user_session = build_user_session(turn)
        other_user_memory = user_session.db.exec(
            select(Memory).where(Memory.user_id == user_session.user_id, Memory.name == "Shared Memory Name")
        ).one()
        assert other_user_memory is not None
        assert not any(is_in_context_message(other_user_memory, message) for message in context_messages)

    with open_turn_context(ctx) as turn:
        user_session = build_user_session(turn)
        current_user_memory = user_session.db.exec(
            select(Memory).where(Memory.user_id == user_session.user_id, Memory.name == "Shared Memory Name")
        ).one()
        current_user_memory_id = current_user_memory.id
        assert any(is_in_context_message(current_user_memory, message) for message in context_messages)
    assert current_user_memory_id is not None
