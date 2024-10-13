import logging
import re
from typing import Any, Optional, Tuple, Type

from sqlmodel import Session
from toolz import pipe
from toolz.curried import map

from elroy.llm.client import query_llm
from elroy.store.data_models import EmbeddableSqlModel
from elroy.store.embeddings import get_closest_vector_match
from elroy.store.message import get_context_messages, replace_context_messages
from elroy.tools.messenger import process_message


def process_test_message(*args, **kwargs) -> str:
    return pipe(
        process_message(*args, **kwargs),
        list,
        "".join,
    )  # type: ignore


def vector_search_by_text(
    session: Session, user_id: int, query: str, table: Type[EmbeddableSqlModel], filter_clause: Any = lambda: True
) -> Optional[EmbeddableSqlModel]:
    from elroy.llm.client import get_embedding

    return get_closest_vector_match(session, user_id, get_embedding(query), table, filter_clause)


def ask_assistant_bool(session: Session, user_id: int, question: str) -> Tuple[bool, str]:
    def get_boolean(response: str, attempt: int = 1) -> bool:
        if attempt > 3:
            raise ValueError("Too many attempts")

        first_word = pipe(
            response,
            lambda _: re.match(r"\w+", _),
            lambda _: _.group(0).lower() if _ else None,
        )

        if first_word in ["true", "yes"]:
            return True
        elif first_word in ["false", "no"]:
            return False
        else:
            logging.info("Attempting to parse response")
            return get_boolean(
                query_llm(
                    system="You are an AI assistant, who converts text responses to boolean. "
                    "Given a piece of text, respond with TRUE if intention of the answer is to be affirmative, "
                    "and FALSE if the intention of the answer is to be in the negative."
                    "The first word of you response MUST be TRUE or FALSE."
                    "Your should follow this with an explanation of your reasoning.",
                    prompt=response,
                ),  # type: ignore
                attempt + 1,
            )

    question += " Your response to this question is being evaluated as part of an automated test. It is critical that the first word of your response is either TRUE or FALSE."

    response = "".join(process_test_message(session, user_id, question))

    # evict question and answer from context
    context_messages = get_context_messages(session, user_id)
    assert isinstance(context_messages, list)
    endpoint_index = -1
    for idx, message in enumerate(context_messages[::-1]):
        if message.role == "user" and message.content == question:
            endpoint_index = idx
            break
    else:
        raise ValueError("Could not find user message in context")

    pipe(
        context_messages,
        map(lambda _: _),
        list,
        lambda _: _[: -(endpoint_index + 1)],
        lambda _: replace_context_messages(session, user_id, _),
    )

    return (get_boolean(response), response)
