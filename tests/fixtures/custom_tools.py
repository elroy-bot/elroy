from pydantic.main import BaseModel

from elroy.core.constants import tool
from elroy.core.ctx import ElroyContext


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


class GameInfo(BaseModel):
    name: str
    genre: str
    rating: float


class GameInfoResponse(BaseModel):
    result: str


@tool
def get_game_info(game: GameInfo) -> GameInfoResponse:
    """Get information about a game.

    Args:
        game (GameInfo): The game to get information about.

    Returns:
        GameInfoResponse: The information about the game.
    """
    return GameInfoResponse(result=f"The game {game.name} is a {game.genre} game with a rating of {game.rating}.")
