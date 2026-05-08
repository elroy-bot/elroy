from ..core.constants import tool
from ..core.turn import TurnContext

DEFAULT_RESTART_RESUME_PROMPT = "Elroy just restarted. Send a brief message that you are back and ready to continue."
DEFAULT_RESTART_RESUME_MESSAGE = DEFAULT_RESTART_RESUME_PROMPT


@tool
def restart_session(turn: TurnContext, resume_message: str = DEFAULT_RESTART_RESUME_PROMPT) -> str:
    """Restart the active Elroy session after the current response completes.

    Args:
        resume_message: Hidden prompt injected after restart to trigger the assistant's first reply

    Returns:
        str: Status message indicating that a restart has been scheduled
    """
    turn.session.restart_state.request(resume_message)
    return "Restart scheduled. Elroy will restart after this response completes."
