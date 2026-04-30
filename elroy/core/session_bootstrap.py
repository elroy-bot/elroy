from .turn import TurnContext


def bootstrap_turn(turn: TurnContext, *, user_exists: bool) -> None:
    from ..cli.chat import onboard_non_interactive
    from ..repository.context_messages.factory import build_context_refresh_orchestrator
    from ..repository.context_messages.session import build_context_message_session
    from ..tools.inline_tools import verify_inline_tool_call_instruct_matches_ctx

    if not user_exists:
        onboard_non_interactive(turn)

    verify_inline_tool_call_instruct_matches_ctx(turn.config, turn.session)
    build_context_refresh_orchestrator(build_context_message_session(turn)).drop_old_context_messages()
