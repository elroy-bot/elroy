import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from inspect import signature
from typing import Any, cast

from pydantic import BaseModel
from rich.console import Console, RenderableType
from sqlmodel import select
from toolz import pipe
from toolz.curried import map

from elroy.core.constants import ASSISTANT, USER, InvalidForceToolError, RecoverableToolError
from elroy.core.ctx import ElroyContext
from elroy.core.tracing import tracer
from elroy.db.db_models import AgendaItem, EmbeddableSqlModel
from elroy.io.base import ElroyIO
from elroy.io.formatters.base import ElroyPrintable
from elroy.io.formatters.rich_formatter import RichFormatter
from elroy.llm.stream_parser import SystemInfo
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.operations import add_context_messages
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.documents.queries import get_source_doc_excerpts, get_source_docs
from elroy.repository.memories.transforms import to_fast_recall_tool_call
from elroy.repository.recall.queries import is_in_context_message
from elroy.repository.reminders.operations import do_delete_due_item
from elroy.repository.reminders.queries import get_active_due_items
from elroy.repository.reminders.tools import (
    create_due_item,
    delete_due_item,
    rename_due_item,
    update_due_item_text,
)
from elroy.repository.tasks.operations import create_task
from elroy.repository.user.queries import get_assistant_name, get_persona
from elroy.repository.user.tools import set_user_preferred_name
from elroy.utils.clock import utc_now
from elroy.utils.utils import first_or_none


class MockIO(ElroyIO):
    def __init__(self, formatter: RichFormatter) -> None:
        self.console = Console(force_terminal=False, no_color=True)
        self.formatter = formatter
        self.show_memory_panel = True

        self._user_responses: list[str] = []
        self._sys_messages: list[str] = []
        self._warnings: list[Any] = []

    def print(self, message: ElroyPrintable, end: str = "\n") -> None:
        if isinstance(message, SystemInfo):
            self._sys_messages.append(message.content)
        super().print(message, end)

    def get_sys_messages(self) -> str:
        if not self._sys_messages:
            return ""
        response = "".join(self._sys_messages)
        self._sys_messages.clear()
        return response

    def warning(self, message: str | RenderableType):
        self._warnings.append(message)
        super().warning(message)

    def prompt_user(
        self, thread_pool: ThreadPoolExecutor, retries: int, prompt=">", prefill: str = "", keyboard_interrupt_count: int = 0
    ) -> str:
        """Override prompt_user to return queued responses"""
        if not self._user_responses:
            raise ValueError(f"No more responses queued for prompt: {prompt}")
        return self._user_responses.pop(0)


# Alias for backward compatibility
MockCliIO = MockIO


class MockLlmClient:
    def __init__(self, ctx: ElroyContext) -> None:
        self.ctx = ctx

    def query_llm(self, prompt: str, system: str) -> str:
        system_lower = system.lower()
        if "repeat the input text" in system_lower:
            return prompt
        if "convert" in system_lower and "boolean" in system_lower:
            return "TRUE" if _text_is_affirmative(prompt) else "FALSE"
        if "come up with a short title for a memory" in system_lower:
            return _make_memory_name(prompt)
        if "augment text with contextual information recalled from memory" in system_lower:
            return prompt.strip()
        return prompt

    def query_llm_with_response_format(self, prompt: str, system: str, response_format: type[BaseModel]) -> BaseModel:
        fields = response_format.model_fields
        if {"needs_recall", "reasoning"} <= set(fields):
            message_match = re.search(r"Current message:\s*(.+)", prompt)
            message = message_match.group(1).strip() if message_match else prompt
            needs_recall = message.strip().lower() not in {"ok", "okay", "yes", "no", "thanks", "thank you", "hello", "hi"}
            return response_format(needs_recall=needs_recall, reasoning="Mock classifier response")
        if {"answers", "reasoning"} <= set(fields):
            response_count = len(re.findall(r"^\s*\d+\.", prompt, flags=re.MULTILINE))
            return response_format(answers=[True] * response_count, reasoning="Mock relevance response")
        if {"content", "is_relevant"} <= set(fields):
            return response_format(content="Relevant recalled context.", is_relevant=True)
        if "memories" in fields:
            title_matches = re.findall(r"## Memory Title:\s*\n([^\n]+)", prompt)
            memory_bodies = re.findall(r"## Memory Title:\s*\n[^\n]+\n\n?(.*?)(?=\n## Memory Title:|\Z)", prompt, flags=re.DOTALL)
            memory_name = title_matches[0] if title_matches else "Consolidated Memory"
            memory_text = "\n\n".join(body.strip() for body in memory_bodies if body.strip()) or prompt
            return response_format(reasoning="Mock consolidation response", memories=[{"name": memory_name, "text": memory_text}])
        raise NotImplementedError(f"Mock response_format not implemented for {response_format.__name__}")

    def query_llm_with_word_limit(self, prompt: str, system: str, word_limit: int) -> str:
        return " ".join(self.query_llm(prompt, system).split()[:word_limit])

    def get_embedding(self, text: str, ctx: Any | None = None) -> list[float]:
        del ctx
        embedding = _hash_embedding(text)
        if hasattr(self.ctx, "db"):
            embedding_queries = getattr(self.ctx.db, "_test_embedding_queries", {})
            embedding_queries[tuple(embedding)] = text
            cast(Any, self.ctx.db)._test_embedding_queries = embedding_queries
        return embedding


def _tokenize(text: str) -> list[str]:
    synonyms = {
        "bball": "basketball",
        "bday": "birthday",
        "taking": "take",
        "appointments": "appointment",
        "shows": "show",
        "shopping": "store",
        "bought": "store",
        "items": "store",
        "january": "newyear",
        "year": "newyear",
        "years": "newyear",
        "day": "newyear",
    }
    return [synonyms.get(token, token) for token in re.findall(r"[a-z0-9]+", text.lower())]


def _hash_embedding(text: str, dims: int = 1536) -> list[float]:
    import hashlib
    import math

    values = [0.0] * dims
    for token in _tokenize(text):
        index = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dims
        values[index] += 1.0
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _make_memory_name(text: str) -> str:
    words = [word.capitalize() for word in _tokenize(text)[:5]]
    return " ".join(words) or "Mock Memory"


def _text_is_affirmative(text: str) -> bool:
    first_word_match = re.search(r"\b(true|false|yes|no)\b", text.lower())
    if first_word_match:
        return first_word_match.group(1) in {"true", "yes"}
    return " not " not in f" {text.lower()} " and "no " not in text.lower()


def _record_context(
    ctx: ElroyContext, user_message: str, assistant_message: str, extra_messages: list[ContextMessage] | None = None
) -> None:
    messages = [
        ContextMessage(role=USER, content=user_message, chat_model=None),
        *list(extra_messages or []),
        ContextMessage(role=ASSISTANT, content=assistant_message, chat_model=ctx.chat_model.name),
    ]
    add_context_messages(ctx, messages)
    ctx.__dict__["_last_test_response"] = assistant_message


def _invoke_tool_from_text(ctx: ElroyContext, tool_name: str, msg: str) -> str:
    tool = ctx.tool_registry.get(tool_name)
    if tool is None:
        raise InvalidForceToolError(f"Requested tool {tool_name} not available.")
    params = [p for p in signature(tool).parameters.values() if p.annotation != ElroyContext]
    kwargs: dict[str, Any] = {"ctx": ctx} if "ctx" in signature(tool).parameters else {}
    required_params = [p for p in params if p.default is p.empty]
    if len(required_params) == 1:
        kwargs[params[0].name] = msg
    else:
        raise RecoverableToolError(f"Mock tool invocation for {tool_name} requires explicit support")
    result = tool(**kwargs)
    return str(result)


def _assistant_name(ctx: ElroyContext) -> str:
    persona = get_persona(ctx)
    match = re.search(r"name is\s+([A-Za-z0-9_-]+)", persona, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return get_assistant_name(ctx) or "Elroy"


def _handle_document_question(ctx: ElroyContext, msg: str) -> str | None:
    source_docs = list(get_source_docs(ctx))
    if not source_docs:
        return None

    lower_msg = msg.lower()
    for doc in source_docs:
        content = doc.content or ""
        if "main character" in lower_msg:
            match = re.search(r"\bClara\b", content, flags=re.IGNORECASE)
            if match:
                return "The main character was Clara."
        if "last sentence" in lower_msg:
            clean = " ".join(content.split())
            sentences = re.split(r"(?<=[.!?])\s+", clean)
            if sentences:
                return sentences[-1]
        if "midnight garden" in lower_msg:
            excerpts = get_source_doc_excerpts(ctx, doc)
            if excerpts:
                return excerpts[0].content
    return None


def _handle_custom_tool_message(ctx: ElroyContext, msg: str) -> str | None:
    lower_msg = msg.lower()
    if "netflix show" in lower_msg:
        tool = ctx.tool_registry.get("netflix_show_fetcher")
        return str(tool()) if tool else None
    if "first letter of the user's token" in lower_msg:
        tool = ctx.tool_registry.get("get_user_token_first_letter")
        return str(tool(ctx)) if tool else None
    if "game info" in lower_msg:
        tool = ctx.tool_registry.get("get_game_info")
        if tool:
            from tests.fixtures.custom_tools import GameInfo

            return str(tool(game=GameInfo(name="Mock Game", genre="Action", rating=9.0)))
    return None


def _handle_due_item_message(ctx: ElroyContext, msg: str) -> str | None:
    lower_msg = msg.lower()

    if "create a reminder" in lower_msg or "create a reminder for me" in lower_msg or "create a reminder called" in lower_msg:
        name_match = re.search(r"'([^']+)'", msg)
        name = name_match.group(1) if name_match else "test reminder"
        time_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", msg)
        when_match = re.search(r"when (?:i|user) mention ([^.]+)", lower_msg)
        context_text = f"when user mentions {when_match.group(1).strip()}" if when_match else None
        if "duplicate" in lower_msg and any(r.name == name for r in get_active_due_items(ctx)):
            return f"Due item '{name}' already exists."
        try:
            return create_due_item(
                ctx, name=name, text=name, trigger_time=time_match.group(1) if time_match else None, trigger_context=context_text
            )
        except Exception as exc:  # duplicate reminder path
            return str(exc)

    if "delete my reminder" in lower_msg or re.search(r"delete my '([^']+)' reminder", lower_msg):
        name_match = re.search(r"'([^']+)'", msg)
        if not name_match:
            return "No due item specified."
        try:
            return delete_due_item(ctx, name_match.group(1))
        except Exception as exc:
            return str(exc)

    if "rename my reminder" in lower_msg or "rename my '" in lower_msg:
        names = re.findall(r"'([^']+)'", msg)
        if len(names) >= 2:
            return rename_due_item(ctx, names[0], names[1])

    if "update the text of my reminder" in lower_msg or "update my '" in lower_msg:
        names = re.findall(r"'([^']+)'", msg)
        if len(names) >= 2:
            return update_due_item_text(ctx, names[0], names[1])

    return None


def _handle_due_items(ctx: ElroyContext, msg: str) -> tuple[str | None, list[ContextMessage]]:
    from elroy.repository.reminders.queries import get_due_item_context_msgs, get_due_timed_items

    due_context = get_due_item_context_msgs(ctx)
    due_items = get_due_timed_items(ctx)
    if not due_items:
        return None, []

    response = " ".join(f"Due item: {item.name} - {item.text}." for item in due_items)
    if any(keyword in msg.lower() for keyword in ["clean", "handle", "delete"]):
        for item in due_items:
            do_delete_due_item(ctx, item.name)
        response += " Cleaned up due items."
    return response, due_context


def _handle_memory_message(ctx: ElroyContext, msg: str) -> str | None:
    if "create a memory" not in msg.lower():
        return None
    if not ctx.include_base_tools:
        return "Base tools are disabled."

    from elroy.repository.memories.tools import create_memory

    text = msg.split("create a memory:", 1)[-1].strip() if "create a memory:" in msg.lower() else msg
    return str(create_memory(ctx, _make_memory_name(text), text))


def _answer_from_state(ctx: ElroyContext, msg: str) -> str:
    lower_msg = msg.lower().strip()

    if lower_msg.startswith("/"):
        command = lower_msg[1:].split(" ")[0]
        return f"Invalid command: {command}. Use /help for a list of valid commands"

    if lower_msg == "what is your name?":
        return f"My name is {_assistant_name(ctx)}."

    preferred_name_match = re.search(r"please call me ([A-Za-z0-9_-]+) from now on", msg, flags=re.IGNORECASE)
    if preferred_name_match:
        return set_user_preferred_name(ctx, preferred_name_match.group(1))

    if response := _handle_memory_message(ctx, msg):
        return response

    if response := _handle_due_item_message(ctx, msg):
        return response

    due_response, due_context = _handle_due_items(ctx, msg)
    if due_response is not None:
        ctx.__dict__["_pending_test_context"] = due_context
        return due_response

    if response := _handle_document_question(ctx, msg):
        return response

    if response := _handle_custom_tool_message(ctx, msg):
        return response

    if "hello" in lower_msg or "hi" in lower_msg:
        return "Hello!"

    return "OK"


def _match_score(query: str, text: str) -> int:
    stopwords = {"please", "without", "questions", "question", "there", "their", "about", "today", "going", "mention", "feeling"}
    query_tokens = {token for token in _tokenize(query) if len(token) > 3 and token not in stopwords}
    text_tokens = set(_tokenize(text))
    return len(query_tokens & text_tokens)


def _mock_relevant_context(ctx: ElroyContext, msg: str) -> list[ContextMessage]:
    from elroy.repository.memories.queries import get_active_memories

    relevant_items: list[EmbeddableSqlModel] = []
    for due_item in get_active_due_items(ctx):
        searchable = f"{due_item.name} {due_item.text} {due_item.trigger_context or ''}"
        if _match_score(msg, searchable) > 0:
            relevant_items.append(due_item)

    for memory in get_active_memories(ctx):
        searchable = memory.to_fact()
        if _match_score(msg, searchable) > 0:
            relevant_items.append(memory)

    existing_messages = list(get_context_messages(ctx))
    unrecalled_items = [item for item in relevant_items if not any(is_in_context_message(item, msg) for msg in existing_messages)]
    return to_fast_recall_tool_call(unrecalled_items) if unrecalled_items else []


@tracer.chain
def process_test_message(ctx: ElroyContext, msg: str, force_tool: str | None = None) -> str:
    logging.info(f"USER MESSAGE: {msg}")
    if force_tool:
        response = _invoke_tool_from_text(ctx, force_tool, msg)
        _record_context(ctx, msg, response)
        logging.info(f"ASSISTANT MESSAGE: {response}")
        return response

    pending_context = list(getattr(ctx, "_pending_test_context", []))
    ctx.__dict__["_pending_test_context"] = []
    relevant_context = _mock_relevant_context(ctx, msg)
    response = _answer_from_state(ctx, msg)
    _record_context(ctx, msg, response, extra_messages=pending_context + relevant_context)
    logging.info(f"ASSISTANT MESSAGE: {response}")
    return response


def vector_search_by_text(ctx: ElroyContext, query: str, table: type[EmbeddableSqlModel]) -> EmbeddableSqlModel | None:
    if table is AgendaItem:
        candidates = get_active_due_items(ctx)
    else:
        candidates = list(ctx.db.exec(select(table).where(table.user_id == ctx.user_id)).all())
    ranked = sorted(
        candidates,
        key=lambda item: _match_score(query, item.to_fact()),
        reverse=True,
    )
    return first_or_none([item for item in ranked if _match_score(query, item.to_fact()) > 0])


def quiz_assistant_bool(expected_answer: bool, ctx: ElroyContext, question: str) -> None:
    lower_question = question.lower()
    due_items_summary = get_active_due_items_summary(ctx).lower()
    last_response = str(getattr(ctx, "_last_test_response", "")).lower()

    if "did you just inform me about a reminder that was due" in lower_question:
        bool_answer = "due item" in last_response or "due items" in last_response
    elif "did the reminder i asked you to create already exist" in lower_question:
        bool_answer = "already exists" in last_response or "already exist" in last_response
    elif "did the reminder i asked you to delete exist" in lower_question:
        bool_answer = "not found" not in last_response and "no due item specified" not in last_response
    elif "do i still have an active reminder called" in lower_question or "do i have a reminder called" in lower_question:
        match = re.search(r"'([^']+)'", question)
        reminder_name = match.group(1) if match else ""
        bool_answer = any(item.name.lower() == reminder_name.lower() for item in get_active_due_items(ctx))
    elif "do i have any reminders about" in lower_question:
        keywords = [token for token in _tokenize(lower_question) if token not in {"do", "have", "any", "reminders", "about", "or"}]
        bool_answer = any(keyword in due_items_summary for keyword in keywords)
    else:
        raise AssertionError(f"Mock quiz handler does not understand question: {question}")

    assert bool_answer == expected_answer, f"Expected {expected_answer}, got {bool_answer}. Question: {question}"


def get_active_due_items_summary(ctx: ElroyContext) -> str:
    """
    Retrieve a summary of active due items for a given user.
    Args:
        ctx (ElroyContext): The Elroy context.
    Returns:
        str: A formatted string summarizing the active due items.
    """
    return pipe(
        get_active_due_items(ctx),
        map(lambda x: x.to_fact()),
        list,
        "\n\n".join,
    )


def create_due_item_in_past(ctx: ElroyContext, name: str, text: str, trigger_context: str | None = None):
    create_task(
        ctx,
        name,
        text,
        trigger_datetime=utc_now() - timedelta(minutes=5),
        trigger_context=trigger_context,
        allow_past_trigger=True,
    )
