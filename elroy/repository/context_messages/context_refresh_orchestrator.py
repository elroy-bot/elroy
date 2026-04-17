import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from typing import Any

from toolz import concatv, pipe
from toolz.curried import tail

from ...config.paths import get_save_dir
from ...core.constants import ASSISTANT, SYSTEM, USER
from ...core.logging import get_logger
from ...llm.client import LlmClient
from ...llm.prompts import summarize_conversation
from ...utils.clock import db_time_to_local, utc_now
from .data_models import ContextMessage
from .queries import ContextMessageQueryService
from .store import ContextMessageStore, retry_on_integrity_error
from .system_prompt_builder import SystemPromptBuilder
from .tools import to_synthetic_tool_call
from .transforms import (
    compress_context_messages,
    format_context_messages,
    is_context_refresh_needed,
)

logger = get_logger()


@dataclass(frozen=True)
class ContextRefreshConfig:
    chat_model_name: str
    max_tokens: int
    context_refresh_target_tokens: int
    max_in_context_message_age: Any
    messages_between_memory: int


@dataclass(frozen=True)
class ContextRefreshMetadataProviders:
    get_assistant_name_fn: Callable[[], str]
    get_user_preferred_name_fn: Callable[[], str | None]


@dataclass(frozen=True)
class ContextRefreshMemoryCallbacks:
    get_or_create_memory_op_tracker_fn: Callable[[], Any]
    schedule_memory_creation_fn: Callable[[], None]
    formulate_memory_fn: Callable[[list[ContextMessage]], tuple[str, str]]
    create_memory_fn: Callable[[str, str], Any]


class ContextRefreshOrchestrator:
    def __init__(
        self,
        query_service: ContextMessageQueryService,
        store: ContextMessageStore,
        system_prompt_builder: SystemPromptBuilder,
        fast_llm: LlmClient,
        config: ContextRefreshConfig,
        metadata_providers: ContextRefreshMetadataProviders,
        memory_callbacks: ContextRefreshMemoryCallbacks,
    ):
        self.query_service = query_service
        self.store = store
        self.fast_llm = fast_llm
        self.system_prompt_builder = system_prompt_builder
        self.config = config
        self.metadata_providers = metadata_providers
        self.memory_callbacks = memory_callbacks
        self.db = query_service.db

    def add_context_message(self, message: ContextMessage) -> None:
        self.add_context_messages([message])

    @retry_on_integrity_error
    def add_context_messages(self, messages: Iterable[ContextMessage]) -> None:
        msgs_list = list(messages)
        user_and_asst_msgs_ct = len([msg for msg in msgs_list if msg.role == USER and msg.content])

        pipe(
            concatv(self.query_service.get_context_messages(), msgs_list),
            self.store.replace_context_messages,
        )

        if user_and_asst_msgs_ct > 0:
            tracker = self.memory_callbacks.get_or_create_memory_op_tracker_fn()
            tracker.messages_since_memory += user_and_asst_msgs_ct
            tracker = self.db.persist(tracker)

            if tracker.messages_since_memory >= self.config.messages_between_memory:
                self.memory_callbacks.schedule_memory_creation_fn()

    def get_refreshed_system_message(self) -> ContextMessage:
        return self.system_prompt_builder.build()

    def context_refresh(self, context_messages: Iterable[ContextMessage]) -> None:
        logger.info("Refreshing context (cache-friendly: preserving system message)")
        context_message_list = list(context_messages)

        memory_title, memory_text = self.memory_callbacks.formulate_memory_fn(context_message_list)
        self.memory_callbacks.create_memory_fn(memory_title, memory_text)

        compressed_messages = pipe(
            context_message_list,
            partial(
                compress_context_messages,
                self.config.chat_model_name,
                self.config.context_refresh_target_tokens,
                self.config.max_in_context_message_age,
            ),
        )

        if len([msg for msg in context_message_list if msg.role == USER]) > 0:
            assistant_name = self.metadata_providers.get_assistant_name_fn()
            conversation_summary = pipe(
                context_message_list[1:],
                lambda msgs: format_context_messages(
                    msgs,
                    self.metadata_providers.get_user_preferred_name_fn() or "User",
                    assistant_name,
                ),
                partial(summarize_conversation, self.fast_llm, assistant_name),
            )

            summary_tool_call = to_synthetic_tool_call(
                func_name="context_summary",
                func_response=f"Recent conversation summary: {conversation_summary}",
            )
            self.store.replace_context_messages(compressed_messages + summary_tool_call)
        else:
            self.store.replace_context_messages(compressed_messages)

    def drop_old_context_messages(self) -> None:
        now = utc_now()
        context_messages = list(self.query_service.get_context_messages())
        to_keep = [
            m
            for m in context_messages
            if m.role == SYSTEM or not m.created_at or m.created_at >= now - self.config.max_in_context_message_age
        ]
        if context_messages and context_messages[0].role != SYSTEM:
            to_keep = [context_messages[0], *[m for m in to_keep if m != context_messages[0]]]
        if len(to_keep) < len(context_messages):
            logger.info(f"Dropping {len(context_messages) - len(to_keep)} messages older than {self.config.max_in_context_message_age}")
            self.store.replace_context_messages(to_keep)

    def refresh_context_if_needed(self) -> None:
        context_messages = list(self.query_service.get_context_messages())
        if is_context_refresh_needed(context_messages, self.config.chat_model_name, self.config.max_tokens):
            self.context_refresh(context_messages)

    def save(self, n: int = 1000) -> str:
        msgs = pipe(
            self.query_service.get_context_messages(),
            tail(n),
            list,
        )

        filename = (
            db_time_to_local(msgs[0].created_at).strftime("%Y-%m-%d_%H-%M-%S")
            + "__"
            + db_time_to_local(msgs[-1].created_at).strftime("%Y-%m-%d_%H-%M-%S")
            + ".json"
        )
        full_path = get_save_dir() / filename

        with full_path.open("w") as f:
            f.write(json.dumps([msg.as_dict() for msg in msgs]))
        return "Saved messages to " + str(full_path)

    def pop(self, n: int) -> str:
        original_list = list(self.query_service.get_context_messages())

        if n <= 0:
            return "Cannot pop 0 or fewer messages"
        if n > len(original_list):
            return f"Cannot pop {n} messages, only {len(original_list)} messages in context"

        context_messages = original_list[:-n]
        if context_messages[-1].role == ASSISTANT and context_messages[-1].tool_calls:
            return f"Popping {n} message would separate an assistant message with a tool call from the tool result. Please pop fewer or more messages."

        self.store.replace_context_messages(context_messages)
        return f"Popped {n} messages from context, new context has {len(list(self.query_service.get_context_messages()))} messages"

    def rewrite(self, new_message: str) -> str:
        if not new_message:
            return "Cannot rewrite message with empty message"

        context_messages = list(self.query_service.get_context_messages())
        if len(context_messages) == 0:
            return "No messages to rewrite"

        i = -1
        while context_messages[i].role != ASSISTANT:
            i -= 1

        context_messages[i] = ContextMessage(role=ASSISTANT, content=new_message, chat_model=None)
        self.store.replace_context_messages(context_messages)
        return "Replaced last assistant message with new message"

    def refresh_system_instructions(self) -> str:
        context_messages = list(self.query_service.get_context_messages())
        if len(context_messages) == 0:
            context_messages.append(self.get_refreshed_system_message())
        else:
            context_messages[0] = self.get_refreshed_system_message()
        self.store.replace_context_messages(context_messages)
        return "System instruction refresh complete"

    def reset_messages(self) -> str:
        logger.info("Resetting messages: Dropping all conversation messages and recalculating system message")
        self.store.replace_context_messages([self.get_refreshed_system_message()])
        return "Context reset complete"
