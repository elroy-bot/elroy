from sqlmodel import desc, select
from tests.utils import process_test_message

from elroy.db.db_models import Reminder


def test_embeddings(george_ctx):

    process_test_message(
        george_ctx,
        "Please create a new reminder for me, 'go to the store'. This is part of a system test, the details of the reminder do not matter. If details are missing, invent them yourself.",
    )

    # Verify that a new embedding was created for the reminder

    reminder = george_ctx.db.exec(select(Reminder).where(Reminder.user_id == george_ctx.user_id).order_by(desc(Reminder.id))).first()

    assert reminder is not None, "Reminder was not created"
    assert isinstance(reminder, Reminder), f"Expected {reminder} to be a Reminder, but got {type(reminder)}"

    assert george_ctx.db.get_embedding(reminder) is not None, "Embedding was not created for the reminder"
    assert george_ctx.db.get_embedding_text_md5(reminder) is not None, "Embedding text MD5 was not created for the reminder"
