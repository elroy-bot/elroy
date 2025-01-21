from elroy.config.constants import tool
from elroy.config.ctx import ElroyContext


# To add a tool, annotate with @tool. A valid docstring is required.
@tool
def netflix_show_fetcher():
    """Returns the name of a Netflix spy show.

    Returns:
        int: The database ID of the memory.
    """
    return "Black Dove"


from langchain_core.tools import tool as lc_tool


@lc_tool
def get_secret_test_answer() -> str:
    """Get the secret test answer

    Returns:
        str: the secret answer

    """
    return "I can't reveal that information at this time."


# To access ElroyContext data, include it as an argument. It does not need to be annotated
@lc_tool
def get_user_token_first_letter(ctx: ElroyContext):
    """Returns the first letter of the user's name.

    Returns:
        str: The first letter of the user's name
    """
    return ctx.user_token[0]
