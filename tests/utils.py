import logging
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, List, Optional, Type, Union

from rich.console import RenderableType
from toolz import pipe
from toolz.curried import do, map

from elroy.config.constants import USER, RecoverableToolError
from elroy.config.ctx import ElroyContext
from elroy.db.db_models import EmbeddableSqlModel
from elroy.io.cli import CliIO
from elroy.io.formatters.base import ElroyPrintable
from elroy.io.formatters.rich_formatter import RichFormatter
from elroy.llm.client import get_embedding, query_llm
from elroy.llm.stream_parser import SystemInfo
from elroy.messenger import process_message
from elroy.repository.context_messages.operations import replace_context_messages
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.goals.queries import get_active_goals
from elroy.repository.recall.queries import query_vector
from elroy.utils.utils import first_or_none


class MockCliIO(CliIO):
    def __init__(self, formatter: RichFormatter) -> None:
        super().__init__(
            formatter=formatter,
            show_internal_thought=False,
        )

        self._user_responses: List[str] = []
        self._sys_messages: List[str] = []
        self._warnings: List[Any] = []

    def print(self, message: ElroyPrintable, end: str = "\n") -> None:
        if isinstance(message, SystemInfo):
            self._sys_messages.append(message.content)
        super().print(message, end)

    def get_sys_messages(self) -> str:
        if not self._sys_messages:
            return ""
        else:
            response = "".join(self._sys_messages)
            self._sys_messages.clear()
            return response

    def add_user_response(self, response: str) -> None:
        """Add a response to the queue of responses"""
        self._user_responses.append(response)

    def add_user_responses(self, *responses: str) -> None:
        """Add multiple responses at once"""
        for response in responses:
            self.add_user_response(response)

    def warning(self, message: Union[str, RenderableType]):
        self._warnings.append(message)
        super().warning(message)

    def prompt_user(
        self, thread_pool: ThreadPoolExecutor, retries: int, prompt=">", prefill: str = "", keyboard_interrupt_count: int = 0
    ) -> str:
        """Override prompt_user to return queued responses"""
        if not self._user_responses:
            raise ValueError(f"No more responses queued for prompt: {prompt}")
        return self._user_responses.pop(0)


def process_test_message(ctx: ElroyContext, msg: str, force_tool: Optional[str] = None) -> str:
    logging.info(f"USER MESSAGE: {msg}")

    return pipe(
        process_message(USER, ctx, msg, force_tool),
        map(lambda _: _.content),
        list,
        "".join,
        do(lambda x: logging.info(f"ASSISTANT MESSAGE: {x}")),
    )  # type: ignore


def vector_search_by_text(ctx: ElroyContext, query: str, table: Type[EmbeddableSqlModel]) -> Optional[EmbeddableSqlModel]:
    return pipe(
        get_embedding(ctx.embedding_model, query),
        partial(query_vector, table, ctx),
        first_or_none,
    )  # type: ignore


def quiz_assistant_bool(expected_answer: bool, ctx: ElroyContext, question: str) -> None:
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
                model=ctx.chat_model,
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

    MAX_ATTEMPTS = 3
    attempt = 1

    full_response = None

    while attempt <= MAX_ATTEMPTS:
        try:
            full_response = "".join(process_test_message(ctx, question))
            break
        except RecoverableToolError as e:
            logging.warning(f"Error processing question: {e}. Retrying")
            question = f"Error: {e}. Try again. Original question: {question}"
            attempt += 1

    if not full_response:
        raise ValueError("Could not process question")

    # evict question and answer from context
    context_messages = list(get_context_messages(ctx))
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
        lambda _: replace_context_messages(ctx, _),
    )

    bool_answer = get_boolean(full_response)

    assert bool_answer == expected_answer, f"Expected {expected_answer}, got {bool_answer}. Full response: {full_response}"


def get_active_goals_summary(ctx: ElroyContext) -> str:
    """
    Retrieve a summary of active goals for a given user.
    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.
    Returns:
        str: A formatted string summarizing the active goals.
    """
    return pipe(
        get_active_goals(ctx),
        map(lambda x: x.to_fact()),
        list,
        "\n\n".join,
    )  # type: ignore
