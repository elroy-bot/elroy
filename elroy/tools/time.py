from ..core.constants import tool
from ..core.ctx import ElroyContext
from ..utils.clock import local_now
from ..utils.utils import datetime_to_string


@tool
def get_current_date(ctx: ElroyContext) -> str:
    """Returns the current date and time.

    Returns:
        str: The current date and time in the format "Day, Month DD, YYYY HH:MM AM/PM TZ"
    """
    return datetime_to_string(local_now())
