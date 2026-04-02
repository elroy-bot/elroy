import uuid
from collections.abc import Iterator
from typing import Any, cast

from pydantic import BaseModel
from toolz import pipe

from ..core.constants import ASSISTANT, SYSTEM, TOOL, USER
from ..core.ctx import ElroyContext
from ..core.latency import LatencyTracker
from ..core.logging import get_logger
from ..core.tracing import tracer
from ..db.db_models import FunctionCall
from ..llm.stream_parser import AssistantInternalThought, AssistantResponse, CodeBlock, StatusUpdate
from ..repository.context_messages.data_models import ContextMessage
from ..repository.context_messages.operations import add_context_messages
from ..repository.context_messages.queries import get_context_messages
from ..repository.context_messages.validations import Validator
from ..repository.memories.queries import get_relevant_memory_context_msgs
from ..repository.memories.recall_classifier import should_recall_memory
from ..repository.reminders.queries import get_due_item_context_msgs
from .tools import exec_function_call

logger = get_logger()


def _tracker(ctx: ElroyContext) -> LatencyTracker:
    tracker = ctx.latency_tracker
    assert isinstance(tracker, LatencyTracker)
    return tracker


def _load_context_messages(ctx: ElroyContext, request_id: str) -> list[ContextMessage]:
    with _tracker(ctx).measure("load_context_messages"):
        context_messages: list[ContextMessage] = pipe(
            get_context_messages(ctx),
            lambda msgs: Validator(ctx, msgs).validated_msgs(),
            list,
        )
        logger.debug(f"[{request_id}] Loaded {len(context_messages)} context messages")
        return context_messages


def _maybe_recall_memories(
    ctx: ElroyContext,
    msg: str,
    context_messages: list[ContextMessage],
    new_msgs: list[ContextMessage],
) -> Iterator[BaseModel]:
    if ctx.memory_config.memory_recall_classifier_enabled:
        yield StatusUpdate(content="classifying recall...")
        with _tracker(ctx).measure("memory_recall_classification"):
            recall_decision = should_recall_memory(
                ctx=ctx,
                current_message=msg,
                recent_messages=context_messages,
            )

        if not recall_decision.needs_recall:
            logger.debug(f"Memory recall skipped: {recall_decision.reasoning}")
            _tracker(ctx).track("memory_recall", 0, skipped=True)
            return

        logger.debug(f"Memory recall enabled: {recall_decision.reasoning}")
        yield StatusUpdate(content="fetching memories...")
        with _tracker(ctx).measure("memory_recall", needs_recall=True):
            new_msgs += get_relevant_memory_context_msgs(ctx, context_messages + new_msgs)
        return

    yield StatusUpdate(content="fetching memories...")
    with _tracker(ctx).measure("memory_recall", classifier_disabled=True):
        new_msgs += get_relevant_memory_context_msgs(ctx, context_messages + new_msgs)


def _emit_internal_thoughts(ctx: ElroyContext, new_msgs: list[ContextMessage]) -> Iterator[AssistantInternalThought]:
    if not ctx.show_internal_thought:
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


def _process_llm_loop(
    ctx: ElroyContext,
    context_messages: list[ContextMessage],
    new_msgs: list[ContextMessage],
    enable_tools: bool,
    force_tool: str | None,
) -> Iterator[BaseModel]:
    loops = 0
    while True:
        function_calls: list[FunctionCall] = []
        tool_context_messages: list[ContextMessage] = []

        with _tracker(ctx).measure("llm_completion", loop=loops):
            llm = cast(Any, ctx.llm)
            stream = llm.generate_chat_completion_message(
                context_messages=context_messages + new_msgs,
                tool_schemas=ctx.tool_registry.get_schemas(),
                enable_tools=enable_tools and (not ctx.chat_model.inline_tool_calls) and loops <= ctx.max_assistant_loops,
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
                    with _tracker(ctx).measure("tool_execution", tool=stream_chunk.function_name):
                        tool_call_result = exec_function_call(ctx, stream_chunk)
                        tool_context_messages.append(
                            ContextMessage(
                                role=TOOL,
                                tool_call_id=stream_chunk.id,
                                content=str(tool_call_result),
                                chat_model=ctx.chat_model.name,
                            )
                        )
                        yield tool_call_result
                    yield StatusUpdate(content="thinking...")

        new_msgs.append(
            ContextMessage(
                role=ASSISTANT,
                content=stream.get_full_text(),
                tool_calls=(None if not function_calls else [f.to_tool_call() for f in function_calls]),
                chat_model=ctx.chat_model.name,
            )
        )

        new_msgs += tool_context_messages
        if force_tool:
            assert tool_context_messages, "force_tool set, but no tool messages generated"
            with _tracker(ctx).measure("persist_context_messages", count=len(new_msgs)):
                add_context_messages(ctx, new_msgs)
            return
        if tool_context_messages:
            loops += 1
            continue
        with _tracker(ctx).measure("persist_context_messages", count=len(new_msgs)):
            add_context_messages(ctx, new_msgs)
        return


@tracer.chain
def process_message(
    *,
    role: str,
    ctx: ElroyContext,
    msg: str,
    enable_tools: bool = True,
    force_tool: str | None = None,
) -> Iterator[BaseModel]:
    assert role in {USER, ASSISTANT, SYSTEM}

    # Initialize latency tracker for this request
    request_id = str(uuid.uuid4())[:8]
    ctx.latency_tracker = LatencyTracker(request_id=request_id)
    logger.info(f"[{request_id}] Processing message (role={role}, length={len(msg)})")

    if force_tool and not enable_tools:
        logger.warning("force_tool set, but enable_tools is False. Ignoring force_tool.")

    yield StatusUpdate(content="loading context...")
    context_messages = _load_context_messages(ctx, request_id)

    new_msgs: list[ContextMessage] = [
        ContextMessage(
            role=role,
            content=msg,
            chat_model=None,
        )
    ]

    yield from _maybe_recall_memories(ctx, msg, context_messages, new_msgs)

    # Check for due timed items and surface them
    with _tracker(ctx).measure("due_items_check"):
        due_item_msgs = get_due_item_context_msgs(ctx)

    if due_item_msgs:
        new_msgs += due_item_msgs

    yield from _emit_internal_thoughts(ctx, new_msgs)

    yield StatusUpdate(content="thinking...")
    yield from _process_llm_loop(ctx, context_messages, new_msgs, enable_tools, force_tool)

    # Log latency summary at the end of processing
    ctx.latency_tracker.log_summary()
