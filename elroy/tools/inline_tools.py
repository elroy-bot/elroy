from typing import Any

from ..core.ctx import ElroyConfig
from ..core.logging import get_logger
from ..core.runtime import build_inline_tool_runtime
from ..core.session import open_turn_context
from ..core.turn import ElroySession

TOOL_CALL_INSTRUCTION_OPEN_TAG = "<tool_call_instructions>"

logger = get_logger()


def verify_inline_tool_call_instruct_matches_ctx(ctx: ElroyConfig, session: ElroySession) -> None:
    # verify system instruct matches startup settings
    from ..repository.context_messages.factory import build_context_refresh_orchestrator
    from ..repository.context_messages.queries import do_get_current_system_instruct
    from ..repository.context_messages.session import build_context_message_session

    runtime = build_inline_tool_runtime(ctx)
    with open_turn_context(ctx, session) as turn:
        context_refresh_orchestrator = build_context_refresh_orchestrator(build_context_message_session(turn))
        system_msg = do_get_current_system_instruct(turn)

        if system_msg is None or system_msg.content is None:
            logger.warning("System instruct message is missing, refreshing system instruct")
            context_refresh_orchestrator.refresh_system_instructions()
        elif runtime.inline_tool_calls and TOOL_CALL_INSTRUCTION_OPEN_TAG not in system_msg.content:
            logger.info("Inline tool calls enabled but instruction not present in system instruct, refreshing system instruct")
            context_refresh_orchestrator.refresh_system_instructions()
        elif not runtime.inline_tool_calls and TOOL_CALL_INSTRUCTION_OPEN_TAG in system_msg.content:
            logger.info("Inline tool calls disabled but instruction present in system instruct, refreshing system instruct")
            context_refresh_orchestrator.refresh_system_instructions()
        else:
            logger.debug("System instruct message matches startup settings")


def inline_tool_instruct(schemas: list[dict[str, Any]]) -> str:
    return (
        "\n".join(["<tool_call_schemas>", *[str(x) for x in schemas], "</tool_call_schemas>"])
        + TOOL_CALL_INSTRUCTION_OPEN_TAG
        + "\n"
        + """
To make tool calls, include the following in your response:
<tool_call>
{"arguments": <args-dict>, "name": <function-name>}
</tool_call>

The tool call MUST BE VALID JSON.

For example, to use a tool to create a memory, you could include the following in your response:
<tool_call>
{"arguments": {"name": "Receiving instructions for tool calling", "text": "Today I learned how to call tools in Elroy."}, "name": "create_memory"}
</tool_call>
<tool_call_instructions>
"""
    )
