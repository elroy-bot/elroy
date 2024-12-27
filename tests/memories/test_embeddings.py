from sqlmodel import desc, select
from tests.utils import process_test_message

from elroy.db.db_models import Goal


def test_embeddings(george_ctx):

    process_test_message(
        george_ctx,
        "Please create a new goal for me, 'go to the store'. This is part of a system test, the details of the goal do not matter. If details are missing, invent them yourself.",
    )

    # Verify that a new embedding was created for the goal

    goal = george_ctx.db.exec(select(Goal).where(Goal.user_id == george_ctx.user_id).order_by(desc(Goal.id))).first()

    assert goal is not None, "Goal was not created"
    assert isinstance(goal, Goal), f"Expected {goal} to be a Goal, but got {type(goal)}"

    assert george_ctx.db.get_embedding(goal) is not None, "Embedding was not created for the goal"
    assert george_ctx.db.get_embedding_text_md5(goal) is not None, "Embedding text MD5 was not created for the goal"
