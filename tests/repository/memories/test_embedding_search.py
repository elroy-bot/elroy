from typing import List

from sqlmodel import select
from tests.conftest import BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME
from tests.utils import process_test_message, vector_search_by_text
from toolz import pipe
from toolz.curried import filter

from elroy.db.db_models import Reminder
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.queries import get_context_messages


def test_reminder_relevance(george_ctx):

    assert vector_search_by_text(george_ctx, "I'm off to go play basketball!", Reminder)
    assert not vector_search_by_text(george_ctx, "I'm off to ride horses!", Reminder)
    assert not vector_search_by_text(george_ctx, "I wonder what time it is", Reminder)
    assert vector_search_by_text(
        george_ctx,
        "Big day today! I'm going to watch a bunch of television, probably 20 shows, might play some bball alter",
        Reminder,
    )
    assert not vector_search_by_text(
        george_ctx, "Elephants swiftly draw vibrant pancakes across whispering oceans under midnight skies.", Reminder
    )


def test_reminder_in_context(george_ctx):
    reminder = george_ctx.db.exec(
        select(Reminder).where(
            Reminder.user_id == george_ctx.user_id,
            Reminder.name == BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME,
        )
    ).one_or_none()
    assert reminder
    reminder_id = reminder.id

    process_test_message(george_ctx, "I'm off to go play basketball!")

    context_messages = list(get_context_messages(george_ctx))

    assert len(messages_with_reminder_id(context_messages, reminder_id)) == 1

    # Ensure we do not redundantly add the same reminder to the context
    process_test_message(george_ctx, "I'm in the car, heading over to play basketball")

    context_messages = list(get_context_messages(george_ctx))

    assert len(messages_with_reminder_id(context_messages, reminder_id)) == 1


def messages_with_reminder_id(context_messages: List[ContextMessage], reminder_id) -> List[ContextMessage]:
    return pipe(
        context_messages,
        filter(
            lambda m: m.memory_metadata
            and any(metadata.id == reminder_id and metadata.memory_type == Reminder.__name__ for metadata in m.memory_metadata)
        ),
        list,
    )
