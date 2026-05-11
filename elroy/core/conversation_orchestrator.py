"""Conversation orchestration for chat message processing."""

import uuid
from collections.abc import Iterator
from typing import Any, cast

from pydantic import BaseModel
from toolz import pipe

from ..db.db_models import FunctionCall
from ..llm.stream_parser import AssistantInternalThought, AssistantResponse, AssistantToolResult, CodeBlock, StatusUpdate
from ..messenger.tools import exec_function_call
from ..repository.context_messages.data_models import ContextMessage
from ..repository.context_messages.factory import (
    build_context_message_read_store,
    build_context_refresh_orchestrator,
)
from ..repository.context_messages.session import build_context_message_session
from ..repository.context_messages.validations import Validator
from ..repository.memories.factory import build_memory_recall_orchestrator
from ..repository.memories.recall_classifier import should_recall_memory
from ..repository.reminders.queries import do_get_due_item_context_msgs
from ..repository.user.queries import do_get_user_preferred_name, get_assistant_name
from ..repository.user.session import build_user_runtime, build_user_session
from .constants import ASSISTANT, SYSTEM, TOOL, USER
from .latency import LatencyTracker
from .logging import get_logger
from .runtime import build_conversation_runtime, build_recall_classifier_runtime
from .turn import TurnContext

logger = get_logger()


class ConversationOrchestrator:
    def __init__(self, turn: TurnContext):
        self.turn = turn
        self.runtime = build_conversation_runtime(turn)
        self.context_session = build_context_message_session(turn)
        self.context_message_read_store = build_context_message_read_store(self.context_session)
        self.context_refresh_orchestrator = build_context_refresh_orchestrator(self.context_session)
        self.memory_recall_orchestrator = build_memory_recall_orchestrator(turn)
        self.user_runtime = build_user_runtime(turn)

    def _tracker(self) -> LatencyTracker:
        tracker = self.turn.latency_tracker
        assert isinstance(tracker, LatencyTracker)
        return tracker

    def _load_context_messages(self, request_id: str) -> list[ContextMessage]:
        with self._tracker().measure("load_context_messages"):
            context_messages: list[ContextMessage] = pipe(
                self.context_message_read_store.get_context_messages(),
                lambda msgs: Validator(self.turn, msgs).validated_msgs(),
                list,
            )
            logger.debug(f"[{request_id}] Loaded {len(context_messages)} context messages")
            return context_messages

    def _build_user_message(self, role: str, msg: str) -> list[ContextMessage]:
        return [
            ContextMessage(
                role=role,
                content=msg,
                chat_model=None,
            )
        ]

    def _maybe_recall_memories(
        self,
        msg: str,
        context_messages: list[ContextMessage],
        new_msgs: list[ContextMessage],
    ) -> Iterator[BaseModel]:
        user_session = build_user_session(self.turn)
        assistant_name = get_assistant_name(user_session, self.user_runtime)
        user_preferred_name = do_get_user_preferred_name(user_session.db.session, user_session.user_id)

        if self.runtime.memory_recall_classifier_enabled:
            yield StatusUpdate(content="classifying recall...")
            with self._tracker().measure("memory_recall_classification"):
                recall_decision = should_recall_memory(
                    runtime=build_recall_classifier_runtime(self.turn),
                    current_message=msg,
                    recent_messages=context_messages,
                )

            if not recall_decision.needs_recall:
                logger.debug(f"Memory recall skipped: {recall_decision.reasoning}")
                self._tracker().track("memory_recall", 0, skipped=True)
                return

            logger.debug(f"Memory recall enabled: {recall_decision.reasoning}")
            yield StatusUpdate(content="fetching memories...")
            with self._tracker().measure("memory_recall", needs_recall=True):
                new_msgs += self.memory_recall_orchestrator.get_relevant_memory_context_msgs(
                    context_messages + new_msgs,
                    assistant_name,
                    user_preferred_name,
                )
            return

        yield StatusUpdate(content="fetching memories...")
        with self._tracker().measure("memory_recall", classifier_disabled=True):
            new_msgs += self.memory_recall_orchestrator.get_relevant_memory_context_msgs(
                context_messages + new_msgs,
                assistant_name,
                user_preferred_name,
            )

    def _append_due_items(self, new_msgs: list[ContextMessage]) -> None:
        with self._tracker().measure("due_items_check"):
            due_item_msgs = do_get_due_item_context_msgs(self.turn)
        if due_item_msgs:
            new_msgs += due_item_msgs

    def _emit_internal_thoughts(self, new_msgs: list[ContextMessage]) -> Iterator[AssistantInternalThought]:
        if not self.runtime.show_internal_thought:
            return

        from ..repository.data_models import RecallResponse

        for new_msg in new_msgs[1:]:
            if not new_msg.content:
                continue
            try:
                recall = RecallResponse.model_validate_json(new_msg.content)
                display_content = recall.content
            except Exception:
                display_content = new_msg.content
            yield AssistantInternalThought(content=display_content)
        yield AssistantInternalThought(content="\n\n")

    def _run_llm_loop(
        self,
        context_messages: list[ContextMessage],
        new_msgs: list[ContextMessage],
        enable_tools: bool,
        force_tool: str | None,
        persist_input_message: bool,
    ) -> Iterator[BaseModel]:
        loops = 0
        while True:
            function_calls: list[FunctionCall] = []
            tool_context_messages: list[ContextMessage] = []

            with self._tracker().measure("llm_completion", loop=loops):
                llm = cast(Any, self.runtime.llm)
                stream = llm.generate_chat_completion_message(
                    context_messages=context_messages + new_msgs,
                    tool_schemas=self.runtime.tool_schemas,
                    enable_tools=enable_tools and (not self.runtime.inline_tool_calls) and loops <= self.runtime.max_assistant_loops,
                    force_tool=force_tool,
                )
                for stream_chunk in stream.process_stream():
                    if isinstance(stream_chunk, (AssistantResponse, AssistantInternalThought, CodeBlock)):
                        yield stream_chunk
                        continue
                    if isinstance(stream_chunk, FunctionCall):
                        yield stream_chunk
                        function_calls.append(stream_chunk)
                        yield StatusUpdate(content=f"running {stream_chunk.function_name}...")
                        with self._tracker().measure("tool_execution", tool=stream_chunk.function_name):
                            tool_call_result = exec_function_call(self.turn, stream_chunk)
                            tool_context_messages.append(
                                ContextMessage(
                                    role=TOOL,
                                    tool_call_id=stream_chunk.id,
                                    content=(
                                        tool_call_result.model_dump_json()
                                        if isinstance(tool_call_result, BaseModel) and not isinstance(tool_call_result, AssistantToolResult)
                                        else str(tool_call_result)
                                    ),
                                    chat_model=self.runtime.chat_model_name,
                                )
                            )
                            yield tool_call_result
                        yield StatusUpdate(content="thinking...")

            new_msgs.append(
                ContextMessage(
                    role=ASSISTANT,
                    content=stream.get_full_text(),
                    tool_calls=(None if not function_calls else [f.to_tool_call() for f in function_calls]),
                    chat_model=self.runtime.chat_model_name,
                )
            )

            new_msgs += tool_context_messages
            if force_tool:
                assert tool_context_messages, "force_tool set, but no tool messages generated"
                with self._tracker().measure("persist_context_messages", count=len(new_msgs)):
                    self.context_refresh_orchestrator.add_context_messages(self._messages_to_persist(new_msgs, persist_input_message))
                return
            if tool_context_messages:
                loops += 1
                continue
            with self._tracker().measure("persist_context_messages", count=len(new_msgs)):
                self.context_refresh_orchestrator.add_context_messages(self._messages_to_persist(new_msgs, persist_input_message))
            return

    def _messages_to_persist(self, new_msgs: list[ContextMessage], persist_input_message: bool) -> list[ContextMessage]:
        if persist_input_message:
            return new_msgs
        return new_msgs[1:]

    def process_message(
        self,
        *,
        role: str,
        msg: str,
        enable_tools: bool = True,
        force_tool: str | None = None,
        persist_input_message: bool = True,
    ) -> Iterator[BaseModel]:
        assert role in {USER, ASSISTANT, SYSTEM}

        request_id = str(uuid.uuid4())[:8]
        object.__setattr__(self.turn, "latency_tracker", LatencyTracker(request_id=request_id))
        logger.info(f"[{request_id}] Processing message (role={role}, length={len(msg)})")

        if force_tool and not enable_tools:
            logger.warning("force_tool set, but enable_tools is False. Ignoring force_tool.")

        yield StatusUpdate(content="loading context...")
        context_messages = self._load_context_messages(request_id)
        new_msgs = self._build_user_message(role, msg)

        yield from self._maybe_recall_memories(msg, context_messages, new_msgs)
        self._append_due_items(new_msgs)
        yield from self._emit_internal_thoughts(new_msgs)

        yield StatusUpdate(content="thinking...")
        yield from self._run_llm_loop(context_messages, new_msgs, enable_tools, force_tool, persist_input_message)

        self._tracker().log_summary()
