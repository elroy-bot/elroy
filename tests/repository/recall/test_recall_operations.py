from sqlmodel import select

from elroy.db.db_models import Memory
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.memories.operations import do_create_memory
from elroy.repository.recall.operations import add_to_current_context_by_name
from elroy.repository.recall.queries import is_in_context_message


def test_add_to_current_context_by_name_scopes_to_current_user(ctx, db_manager, chat_model_name, tmp_path):
    do_create_memory(ctx, "Shared Memory Name", "Current user memory", [], False)

    other_ctx = ctx.init(
        user_token="other-user-token",
        database_url=db_manager.url,
        chat_model=chat_model_name,
        use_background_threads=True,
        memory_dir=str(tmp_path / "other-memories"),
    )
    other_ctx.set_db_session(ctx.db)
    other_ctx.__dict__["llm"] = ctx.llm
    other_ctx.__dict__["fast_llm"] = ctx.fast_llm

    other_memory = do_create_memory(other_ctx, "Shared Memory Name", "Other user memory", [], False)
    assert other_memory.id is not None

    add_to_current_context_by_name(ctx, "Shared Memory Name", Memory)

    context_messages = list(get_context_messages(ctx))
    assert not any(is_in_context_message(other_memory, message) for message in context_messages)

    current_user_memory = ctx.db.exec(select(Memory).where(Memory.user_id == ctx.user_id, Memory.name == "Shared Memory Name")).one()
    assert current_user_memory.id is not None
    assert any(is_in_context_message(current_user_memory, message) for message in context_messages)

    other_ctx.unset_db_session()
