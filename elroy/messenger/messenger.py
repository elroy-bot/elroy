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
from ..llm.stream_parser import AssistantInternalThought, AssistantResponse, CodeBlock
from ..repository.context_messages.data_models import ContextMessage
from ..repository.context_messages.operations import add_context_messages
from ..repository.context_messages.queries import get_context_messages
from ..repository.context_messages.validations import Validator
from ..repository.memories.queries import get_relevant_memory_context_msgs
from ..repository.memories.recall_classifier import should_recall_memory
from ..repository.reminders.queries import get_due_reminder_context_msgs
from .tools import exec_function_call

logger = get_logger()


@tracer.chain
def process_message(
    *,
    role: str,
    ctx: ElroyContext,
    msg: str,
    enable_tools: bool = True,
    force_tool: str | None = None,
) -> Iterator[BaseModel]:
    assert role in [USER, ASSISTANT, SYSTEM]

    # Initialize latency tracker for this request
    request_id = str(uuid.uuid4())[:8]
    ctx.latency_tracker = LatencyTracker(request_id=request_id)
    logger.info(f"[{request_id}] Processing message (role={role}, length={len(msg)})")

    if force_tool and not enable_tools:
        logger.warning("force_tool set, but enable_tools is False. Ignoring force_tool.")

    with ctx.latency_tracker.measure("load_context_messages"):
        context_messages: list[ContextMessage] = pipe(
            get_context_messages(ctx),
            lambda msgs: Validator(ctx, msgs).validated_msgs(),
            list,
        )
        logger.debug(f"[{request_id}] Loaded {len(context_messages)} context messages")

    new_msgs: list[ContextMessage] = [
        ContextMessage(
            role=role,
            content=msg,
            chat_model=None,
        )
    ]

    # Use classifier to determine if memory recall is necessary
    if ctx.memory_config.memory_recall_classifier_enabled:
        with ctx.latency_tracker.measure("memory_recall_classification"):
            recall_decision = should_recall_memory(
                ctx=ctx,
                current_message=msg,
                recent_messages=context_messages,
            )

        if recall_decision.needs_recall:
            logger.debug(f"Memory recall enabled: {recall_decision.reasoning}")
            with ctx.latency_tracker.measure("memory_recall", needs_recall=True):
                new_msgs += get_relevant_memory_context_msgs(ctx, context_messages + new_msgs)
        else:
            logger.debug(f"Memory recall skipped: {recall_decision.reasoning}")
            ctx.latency_tracker.track("memory_recall", 0, skipped=True)
    else:
        # Classifier disabled, always do recall (backward compatibility)
        with ctx.latency_tracker.measure("memory_recall", classifier_disabled=True):
            new_msgs += get_relevant_memory_context_msgs(ctx, context_messages + new_msgs)

    # Check for due timed reminders and surface them
    with ctx.latency_tracker.measure("due_reminders_check"):
        due_reminder_msgs = get_due_reminder_context_msgs(ctx)

    if due_reminder_msgs:
        new_msgs += due_reminder_msgs

    if ctx.show_internal_thought:
        for new_msg in new_msgs[1:]:
            if new_msg.content:
                yield AssistantInternalThought(content=new_msg.content)
        yield AssistantInternalThought(content="\n\n")  # empty line to separate internal thoughts from assistant responses

    loops = 0
    while True:
        # new_msgs accumulates across all loops, so we can only store new messages once
        # tool_context_messages and function_calls reset each loop: we need to keep track so we can determine whether we need to continue looping
        function_calls: list[FunctionCall] = []
        tool_context_messages: list[ContextMessage] = []

        with ctx.latency_tracker.measure("llm_completion", loop=loops):
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
                elif isinstance(stream_chunk, FunctionCall):
                    yield stream_chunk  # yield the call

                    function_calls.append(stream_chunk)
                    # Note: there's some slightly weird behavior here if the tool call results in context messages being added.
                    # Since we're not persisting new context messages until the end of this loop, context messages from within
                    # tool call executions will show up before the user message it's responding to.
                    with ctx.latency_tracker.measure("tool_execution", tool=stream_chunk.function_name):
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
            with ctx.latency_tracker.measure("persist_context_messages", count=len(new_msgs)):
                add_context_messages(ctx, new_msgs)

            break  # we are specifically requesting tool call results, so don't need to loop for assistant response
        elif tool_context_messages:
            # do NOT persist context messages with add_context_messages at this point, we are continuing to loop and accumulate new msgs
            loops += 1
        else:
            with ctx.latency_tracker.measure("persist_context_messages", count=len(new_msgs)):
                add_context_messages(ctx, new_msgs)
            break

    # Log latency summary at the end of processing
    ctx.latency_tracker.log_summary()
