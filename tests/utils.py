import logging
import re
from functools import partial
from typing import Optional, Type

from toolz import pipe
from toolz.curried import do, map

from elroy.config.config import ElroyContext
from elroy.llm.client import get_embedding, query_llm
from elroy.messaging.messenger import process_message
from elroy.repository.data_models import USER, EmbeddableSqlModel
from elroy.repository.embeddings import query_vector
from elroy.repository.message import get_context_messages, replace_context_messages
from elroy.utils.utils import first_or_none


def process_test_message(context: ElroyContext, msg: str) -> str:
    logging.info(f"USER MESSAGE: {msg}")

    return pipe(
        process_message(context, msg),
        list,
        "".join,
        do(lambda x: logging.info(f"ASSISTANT MESSAGE: {x}")),
    )  # type: ignore


def vector_search_by_text(context: ElroyContext, query: str, table: Type[EmbeddableSqlModel]) -> Optional[EmbeddableSqlModel]:
    return pipe(
        get_embedding(context.config.embedding_model, query),
        partial(query_vector, table, context),
        first_or_none,
    )  # type: ignore


def assert_assistant_bool(expected_answer: bool, context: ElroyContext, question: str) -> None:
    def get_boolean(response: str, attempt: int = 1) -> bool:
        if attempt > 3:
            raise ValueError("Too many attempts")

        for line in response.split("\n"):
            first_word = pipe(
                line,
                lambda _: re.match(r"\w+", _),
                lambda _: _.group(0).lower() if _ else None,
            )

            if first_word in ["true", "yes"]:
                return True
            elif first_word in ["false", "no"]:
                return False
        logging.info("Retrying boolean answer parsing")
        return get_boolean(
            query_llm(
                model=context.config.chat_model,
                system="You are an AI assistant, who converts text responses to boolean. "
                "Given a piece of text, respond with TRUE if intention of the answer is to be affirmative, "
                "and FALSE if the intention of the answer is to be in the negative."
                "The first word of you response MUST be TRUE or FALSE."
                "Your should follow this with an explanation of your reasoning."
                "For example, if the question is, is the 1 greater than 0, your answer could be:"
                "TRUE: 1 is greater than 0 as per basic math.",
                prompt=response,
            ),  # type: ignore
            attempt + 1,
        )

    question += " Your response to this question is being evaluated as part of an automated test. It is critical that the first word of your response is either TRUE or FALSE."

    full_response = "".join(process_test_message(context, question))

    # evict question and answer from context
    context_messages = get_context_messages(context)
    assert isinstance(context_messages, list)
    endpoint_index = -1
    for idx, message in enumerate(context_messages[::-1]):
        if message.role == USER and message.content == question:
            endpoint_index = idx
            break
    else:
        raise ValueError("Could not find user message in context")

    pipe(
        context_messages,
        map(lambda _: _),
        list,
        lambda _: _[: -(endpoint_index + 1)],
        lambda _: replace_context_messages(context, _),
    )

    bool_answer = get_boolean(full_response)

    assert bool_answer == expected_answer, f"Expected {expected_answer}, got {bool_answer}. Full response: {full_response}"


def assert_true(context: ElroyContext, question: str) -> None:
    assert_assistant_bool(True, context, question)


def assert_false(context: ElroyContext, question: str) -> None:
    assert_assistant_bool(False, context, question)
