import logging
import re
from functools import partial
from typing import List, Optional, Type, Union

from rich.pretty import Pretty
from toolz import pipe
from toolz.curried import do, map

from elroy.config.config import ElroyContext
from elroy.io.cli import CliIO
from elroy.llm.client import get_embedding, query_llm
from elroy.messaging.messenger import process_message
from elroy.repository.data_models import USER, EmbeddableSqlModel
from elroy.repository.embeddings import query_vector
from elroy.repository.message import get_context_messages, replace_context_messages
from elroy.utils.utils import first_or_none


class TestCliIO(CliIO):
    def __init__(self, *args, **kwargs):
        super().__init__(
            show_internal_thought_monologue=False,
            system_message_color="blue",
            assistant_message_color="green",
            user_input_color="red",
            warning_color="yellow",
            internal_thought_color="magenta",
        )
        self._user_responses: List[str] = []
        self._sys_messages: List[str] = []

    def sys_message(self, message: Union[str, Pretty]) -> None:
        """Override sys_message to store messages"""
        self._sys_messages.append(str(message))
        return super().sys_message(message)

    def add_user_response(self, response: str) -> None:
        """Add a response to the queue of responses"""
        self._user_responses.append(response)

    def add_user_responses(self, *responses: str) -> None:
        """Add multiple responses at once"""
        for response in responses:
            self.add_user_response(response)

    def get_sys_messages(self) -> List[str]:
        """Return all system messages"""
        return self._sys_messages

    def clear_responses(self) -> None:
        """Clear any remaining responses"""
        self._user_responses.clear()

    async def prompt_user(self, prompt=">", prefill: str = "", keyboard_interrupt_count: int = 0) -> str:
        """Override prompt_user to return queued responses"""
        if not self._user_responses:
            raise ValueError(f"No more responses queued for prompt: {prompt}")
        return self._user_responses.pop(0)


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
