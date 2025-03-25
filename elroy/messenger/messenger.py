from typing import Iterator, List, Optional, Union

from toolz import pipe

from ..core.constants import ASSISTANT, SYSTEM, TOOL, USER
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..core.tracing import tracer
from ..db.db_models import FunctionCall
from ..llm.client import generate_chat_completion_message
from ..llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
)
from ..repository.context_messages.data_models import ContextMessage
from ..repository.context_messages.operations import add_context_messages
from ..repository.context_messages.queries import get_context_messages
from ..repository.context_messages.validations import Validator
from ..repository.memories.queries import get_relevant_memory_context_msgs
from .tools import exec_function_call

logger = get_logger()


@tracer.chain
def process_message(
    role: str,
    ctx: ElroyContext,
    msg: str,
    enable_tools: bool = True,
    force_tool: Optional[str] = None,
) -> Iterator[Union[AssistantResponse, AssistantInternalThought, CodeBlock, AssistantToolResult, FunctionCall]]:
    assert role in [USER, ASSISTANT, SYSTEM]

    if force_tool and not enable_tools:
        logger.warning("force_tool set, but enable_tools is False. Ignoring force_tool.")

    context_messages: List[ContextMessage] = pipe(
        get_context_messages(ctx),
        lambda msgs: Validator(ctx, msgs).validated_msgs(),
        list,
    )  # type: ignore

    new_msgs: List[ContextMessage] = [
        ContextMessage(
            role=role,
            content=msg,
            chat_model=None,
        )
    ]
    new_msgs += get_relevant_memory_context_msgs(ctx, context_messages + new_msgs)

    if ctx.show_internal_thought:
        for new_msg in new_msgs[1:]:
            if new_msg.content:
                yield AssistantInternalThought(new_msg.content)
        yield AssistantInternalThought("\n\n")  # empty line to separate internal thoughts from assistant responses

    loops = 0
    while True:
        # new_msgs accumulates across all loops, so we can only store new messages once
        # tool_context_messages and function_calls reset each loop: we need to keep track so we can determine whether we need to continue looping
        function_calls: List[FunctionCall] = []
        tool_context_messages: List[ContextMessage] = []

        stream = generate_chat_completion_message(
            chat_model=ctx.chat_model,
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
                tool_call_result = exec_function_call(ctx, stream_chunk)
                tool_context_messages.append(
                    ContextMessage(
                        role=TOOL,
                        tool_call_id=stream_chunk.id,
                        content=tool_call_result.content,
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
            add_context_messages(ctx, new_msgs)

            break  # we are specifically requesting tool call results, so don't need to loop for assistant response
        elif tool_context_messages:
            # do NOT persist context messages with add_context_messages at this point, we are continuing to loop and accumulate new msgs
            loops += 1
        else:
            add_context_messages(ctx, new_msgs)
            break
