import json
import time
import traceback
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from functools import partial, wraps
from typing import Any, TypeVar, cast

from sqlmodel import select
from toolz import concatv, pipe
from toolz.curried import tail

from ...config.paths import get_save_dir
from ...core.async_tasks import schedule_task
from ...core.constants import (
    ASSISTANT,
    FORMATTING_INSTRUCT,
    SYSTEM,
    SYSTEM_INSTRUCTION_LABEL,
    SYSTEM_INSTRUCTION_LABEL_END,
    USER,
    user_only_tool,
)
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import ContextMessageSet
from ...llm.client import LlmClient
from ...llm.prompts import summarize_conversation
from ...tools.inline_tools import inline_tool_instruct
from ...tools.registry import ToolRegistry
from ...utils.clock import db_time_to_local, utc_now
from ..memories.operations import (
    create_mem_from_current_context,
    formulate_memory,
    get_or_create_memory_op_tracker,
)
from ..memories.tools import create_memory
from ..user.queries import do_get_user_preferred_name, get_assistant_name, get_persona
from .data_models import ContextMessage
from .queries import ContextMessageQueryService
from .tools import to_synthetic_tool_call
from .transforms import (
    compress_context_messages,
    context_message_to_db_message,
    format_context_messages,
    is_context_refresh_needed,
    remove,
)

logger = get_logger()

T = TypeVar("T")


@dataclass(frozen=True)
class ContextMessageOperationConfig:
    chat_model_name: str
    chat_model_inline_tool_calls: bool
    max_tokens: int
    context_refresh_target_tokens: int
    max_in_context_message_age: Any
    messages_between_memory: int


@dataclass(frozen=True)
class ContextMessageMetadataProviders:
    get_persona_fn: Callable[[], str]
    get_assistant_name_fn: Callable[[], str]
    get_user_preferred_name_fn: Callable[[], str | None]


@dataclass(frozen=True)
class ContextMessageMemoryCallbacks:
    get_or_create_memory_op_tracker_fn: Callable[[], Any]
    schedule_memory_creation_fn: Callable[[], None]
    formulate_memory_fn: Callable[[list[ContextMessage]], tuple[str, str]]
    create_memory_fn: Callable[[str, str], Any]


def retry_on_integrity_error[T](fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(self: "ContextMessageOperationService", *args: Any, **kwargs: Any) -> T:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return fn(self, *args, **kwargs)
            except Exception:
                if attempt == max_retries - 1:
                    self.db.rollback()
                    raise
                self.db.rollback()
                time.sleep(0.1 * 2**attempt)
                logger.info(f"Retrying on integrity error (attempt {attempt + 1}/{max_retries})")
        return fn(self, *args, **kwargs)

    return wrapper


class ContextMessageOperationService:
    def __init__(
        self,
        query_service: ContextMessageQueryService,
        tool_registry: ToolRegistry,
        fast_llm: LlmClient,
        config: ContextMessageOperationConfig,
        metadata_providers: ContextMessageMetadataProviders,
        memory_callbacks: ContextMessageMemoryCallbacks,
    ):
        self.query_service = query_service
        self.db = query_service.db
        self.user_id = query_service.user_id
        self.tool_registry = tool_registry
        self.fast_llm = fast_llm
        self.config = config
        self.metadata_providers = metadata_providers
        self.memory_callbacks = memory_callbacks

    def persist_messages(self, messages: Iterable[ContextMessage]) -> Iterator[int]:
        for msg in messages:
            if not msg.content and not msg.tool_calls:
                logger.info(f"Skipping message with no content or tool calls: {msg}\n{traceback.format_exc()}")
            elif msg.id:
                yield msg.id
            else:
                db_message = self.db.persist(context_message_to_db_message(self.user_id, msg))
                assert db_message.id
                yield db_message.id

    def replace_context_messages(self, messages: Iterable[ContextMessage]) -> None:
        msg_ids = list(self.persist_messages(messages))

        existing_context = self.db.exec(
            select(ContextMessageSet).where(
                ContextMessageSet.user_id == self.user_id,
                cast(Any, ContextMessageSet.is_active),
            )
        ).first()

        if existing_context:
            existing_context.is_active = None
            self.db.add(existing_context)
            self.db.session.flush()

        new_context = ContextMessageSet(
            user_id=self.user_id,
            message_ids=json.dumps(msg_ids),
            is_active=True,
        )
        self.db.add(new_context)
        self.db.commit()

    @retry_on_integrity_error
    def remove_context_messages(self, messages: list[ContextMessage]) -> None:
        if not messages:
            return

        logger.info(f"Removing {len(messages)} messages")
        assert all(m.id is not None for m in messages), "All messages must have an id to be removed"

        msg_ids = [m.id for m in messages]
        self.replace_context_messages([m for m in self.query_service.get_context_messages() if m.id not in msg_ids])

    def add_context_message(self, message: ContextMessage) -> None:
        self.add_context_messages([message])

    @retry_on_integrity_error
    def add_context_messages(self, messages: Iterable[ContextMessage]) -> None:
        msgs_list = list(messages)
        user_and_asst_msgs_ct = len([msg for msg in msgs_list if msg.role == USER and msg.content])

        pipe(
            concatv(self.query_service.get_context_messages(), msgs_list),
            self.replace_context_messages,
        )

        if user_and_asst_msgs_ct > 0:
            tracker = self.memory_callbacks.get_or_create_memory_op_tracker_fn()
            tracker.messages_since_memory += user_and_asst_msgs_ct
            tracker = self.db.persist(tracker)

            if tracker.messages_since_memory >= self.config.messages_between_memory:
                self.memory_callbacks.schedule_memory_creation_fn()

    def get_refreshed_system_message(self) -> ContextMessage:
        return pipe(
            [
                SYSTEM_INSTRUCTION_LABEL,
                f"<persona>{self.metadata_providers.get_persona_fn()}</persona>",
                FORMATTING_INSTRUCT,
                inline_tool_instruct(self.tool_registry.get_schemas()) if self.config.chat_model_inline_tool_calls else None,
                "From now on, converse as your persona.",
                SYSTEM_INSTRUCTION_LABEL_END,
            ],
            remove(lambda _: _ is None),
            list,
            "\n".join,
            lambda x: ContextMessage(role=SYSTEM, content=x, chat_model=None),
        )

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
            self.replace_context_messages(compressed_messages + summary_tool_call)
        else:
            self.replace_context_messages(compressed_messages)

    def drop_old_context_messages(self) -> None:
        now = utc_now()
        context_messages = list(self.query_service.get_context_messages())
        to_keep = [
            m
            for m in context_messages
            if m.role == SYSTEM or not m.created_at or m.created_at >= now - self.config.max_in_context_message_age
        ]
        if len(to_keep) < len(context_messages):
            logger.info(f"Dropping {len(context_messages) - len(to_keep)} messages older than {self.config.max_in_context_message_age}")
            self.replace_context_messages(to_keep)

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

        self.replace_context_messages(context_messages)
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
        self.replace_context_messages(context_messages)
        return "Replaced last assistant message with new message"

    def refresh_system_instructions(self) -> str:
        context_messages = list(self.query_service.get_context_messages())
        if len(context_messages) == 0:
            context_messages.append(self.get_refreshed_system_message())
        else:
            context_messages[0] = self.get_refreshed_system_message()
        self.replace_context_messages(context_messages)
        return "System instruction refresh complete"

    def reset_messages(self) -> str:
        logger.info("Resetting messages: Dropping all conversation messages and recalculating system message")
        self.replace_context_messages([self.get_refreshed_system_message()])
        return "Context reset complete"


def _service(ctx: ElroyContext) -> ContextMessageOperationService:
    query_service = ContextMessageQueryService(ctx.db, ctx.user_id)
    return ContextMessageOperationService(
        query_service=query_service,
        tool_registry=ctx.tool_registry,
        fast_llm=ctx.fast_llm,
        config=ContextMessageOperationConfig(
            chat_model_name=ctx.chat_model.name,
            chat_model_inline_tool_calls=ctx.chat_model.inline_tool_calls,
            max_tokens=ctx.max_tokens,
            context_refresh_target_tokens=ctx.context_refresh_target_tokens,
            max_in_context_message_age=ctx.max_in_context_message_age,
            messages_between_memory=ctx.messages_between_memory,
        ),
        metadata_providers=ContextMessageMetadataProviders(
            get_persona_fn=lambda: get_persona(ctx),
            get_assistant_name_fn=lambda: get_assistant_name(ctx),
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(ctx.db.session, ctx.user_id),
        ),
        memory_callbacks=ContextMessageMemoryCallbacks(
            get_or_create_memory_op_tracker_fn=lambda: get_or_create_memory_op_tracker(ctx),
            schedule_memory_creation_fn=lambda: schedule_task(create_mem_from_current_context, ctx),
            formulate_memory_fn=lambda context_messages: formulate_memory(ctx, context_messages),
            create_memory_fn=lambda name, text: create_memory(ctx, name, text),
        ),
    )


def persist_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> Iterator[int]:
    return _service(ctx).persist_messages(messages)


def replace_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    _service(ctx).replace_context_messages(messages)


def remove_context_messages(ctx: ElroyContext, messages: list[ContextMessage]) -> None:
    _service(ctx).remove_context_messages(messages)


def add_context_message(ctx: ElroyContext, message: ContextMessage) -> None:
    _service(ctx).add_context_message(message)


def add_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    _service(ctx).add_context_messages(messages)


def get_refreshed_system_message(ctx: ElroyContext) -> ContextMessage:
    return _service(ctx).get_refreshed_system_message()


def context_refresh(ctx: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    _service(ctx).context_refresh(context_messages)


def drop_old_context_messages(ctx: ElroyContext) -> None:
    _service(ctx).drop_old_context_messages()


def refresh_context_if_needed(ctx: ElroyContext):
    _service(ctx).refresh_context_if_needed()


@user_only_tool
def save(ctx: ElroyContext, n: int = 1000) -> str:
    """
    Saves the last n message from context.
    """
    return _service(ctx).save(n)


@user_only_tool
def pop(ctx: ElroyContext, n: int) -> str:
    """
    Removes the last n messages from the context

    Args:
        n (int): The number of messages to remove

    Returns:
       str: The result of the pop operation.
    """
    return _service(ctx).pop(n)


@user_only_tool
def rewrite(ctx: ElroyContext, new_message: str) -> str:
    """
    Replaces the last message assistant in the context with the new message
        new_message (str): The new message to replace the last message with

    Returns:
        str: The result of the rewrite operation
    """
    return _service(ctx).rewrite(new_message)


@user_only_tool
def refresh_system_instructions(ctx: ElroyContext) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """
    return _service(ctx).refresh_system_instructions()


@user_only_tool
def reset_messages(ctx: ElroyContext) -> str:
    """Resets the context for the user, removing all messages from the context except the system message.
    This should be used sparingly, only at the direct request of the user.

    Args:
        user_id (int): user id

    Returns:
        str: The result of the context reset
    """
    return _service(ctx).reset_messages()
