import enum
from typing import Callable, Dict, List, ParamSpec, TypeVar

MEMORY_WORD_COUNT_LIMIT = 300


# In system persona, the string to replace with the actual user alias
USER_ALIAS_STRING = "$USER_ALIAS"

ASSISTANT_ALIAS_STRING = "$ASSISTANT_ALIAS"  # String to replace in system instructions

SYSTEM_INSTRUCTION_LABEL = "<system_instruction>"
SYSTEM_INSTRUCTION_LABEL_END = "</system_instruction>"

DEFAULT_USER_NAME = "User"

# Message roles
USER, ASSISTANT, TOOL, SYSTEM = ["user", "assistant", "tool", "system"]


### Model parameters ###

# TODO: make this dynamic
EMBEDDING_SIZE = 1536


RESULT_SET_LIMIT_COUNT = 5

REPO_ISSUES_URL = "https://github.com/elroy-bot/elroy/issues"

BUG_REPORT_LOG_LINES = 15


MODEL_SELECTION_CONFIG_PANEL = "Model Selection and Configuration"

EXIT = "exit"

MAX_CHAT_COMPLETION_RETRY_COUNT = 2

IS_TOOL = "_is_tool"
IS_ENABLED = "_is_enabled"
IS_USER_ONLY_TOOL = "_is_user_only_tool"
AUTOCOMPLETE_TYPE = "_autocomplete_type"


class AutocompleteType(enum.Enum):
    "What the args should be autocompleted for this tool"

    NONE = "none"
    IN_CONTEXT_GOALS = "in_context_goals"
    NON_CONTEXT_GOALS = "non_context_goals"
    ALL_ACTIVE_GOALS = "all_active_goals"
    IN_CONTEXT_MEMORIES = "in_context_memories"
    NON_CONTEXT_MEMORIES = "non_context_memories"
    ALL_ACTIVE_MEMORIES = "all_active_memories"


T = TypeVar("T")  # Return type
P = ParamSpec("P")  # Parameters


def autocomplete(autocomplete_type: AutocompleteType) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        setattr(func, AUTOCOMPLETE_TYPE, autocomplete_type)
        return func

    return decorator


# Empty decorator just meaning to communicate a function should be a tool
def tool(func: Callable) -> Callable:
    from .tracing import tracer

    setattr(func, IS_TOOL, True)
    return tracer.tool(func)


# Conveys that the tool is disabled
def disabled_tool(func: Callable) -> Callable:
    setattr(func, IS_TOOL, True)
    setattr(func, IS_ENABLED, False)
    return func


def user_only_tool(func: Callable) -> Callable:
    setattr(func, IS_USER_ONLY_TOOL, True)
    return func


def allow_unused(func: Callable) -> Callable:
    setattr(func, "_allow_unused", True)
    return func


class MissingToolCallMessageError(Exception):
    pass


class InvalidForceToolError(Exception):
    pass


class MaxRetriesExceededError(Exception):
    pass


class RecoverableToolError(Exception):
    """Exceptions in tool calls that the assistant can learn from and correct"""


class GoalAlreadyExistsError(RecoverableToolError):
    def __init__(self, goal_name: str):
        super().__init__(f"Error: Goal with name '{goal_name}' already exists")


class GoalDoesNotExistError(RecoverableToolError):
    def __init__(self, goal_name: str, valid_goal_names: List[str]):
        msg = f"Error: Goal with name '{goal_name}' does not exist."
        msg += f" Valid goal names: {valid_goal_names}" if valid_goal_names else " No goals have been created yet"
        super().__init__(msg)


class Provider(enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    AZURE = "azure"
    OTHER = "other"


GEMINI_PREFIX = "gemini"
AZURE_PREFIX = "azure"

CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
GPT_4O = "gpt-4o"
GEMINI_2_0_FLASH = "gemini/gemini-2.0-flash"
TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
GEMINI_TEXT_EMBEDDING_004 = "gemini/text-embedding-004"


KNOWN_MODELS: Dict[Provider, List[str]] = {
    Provider.OPENAI: [
        # O1 Models
        "o1",
        "o1-2024-12-17",
        "o1-preview",
        "o1-preview-2024-09-12",
        "o1-mini",
        "o1-mini-2024-09-12",
        # GPT-4O Models
        GPT_4O,
        "gpt-4o-2024-11-20",
        "gpt-4o-2024-08-06",
        "gpt-4o-2024-05-13",
        "gpt-4o-realtime-preview",
        "gpt-4o-mini-realtime-preview",
        "gpt-4o-realtime-preview-2024-12-17",
        "gpt-4o-mini-realtime-preview-2024-12-17",
        "gpt-4o-realtime-preview-2024-10-01",
        "gpt-4o-mini",
        "gpt-4o-mini-2024-07-18",
        # GPT-4 Models
        "gpt-4-turbo-preview",
        "gpt-4-turbo",
        "gpt-4-turbo-2024-04-09",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4",
        "gpt-4-32k",
        "gpt-4-1106-preview",
        "gpt-4-0125-preview",
        # GPT-3.5 Models
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-3.5-turbo-0301",
        "gpt-3.5-turbo-0125",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        TEXT_EMBEDDING_3_SMALL,
        "text-embedding-3-large,",
    ],
    Provider.ANTHROPIC: [
        CLAUDE_3_5_SONNET,
        "claude-3",
        "claude-3-opus-20240229",
        "claude-3-5-sonnet-20240620",
        "claude-3-sonnet-20240229",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307",
        "claude-2.1",
        "claude-2",
        "claude-instant-1.2",
        "claude-instant-1",
    ],
    Provider.GEMINI: [
        "gemini/gemini-pro",
        "gemini/gemini-1.5-pro-latest",
        GEMINI_2_0_FLASH,
        "gemini/gemini-2.0-flash-exp",
        "gemini/gemini-2.0-flash-lite-preview-02-05",
        GEMINI_TEXT_EMBEDDING_004,
    ],
}


FORMATTING_INSTRUCT = """
<formatting>
Include in your response internal thoughts. Indicate internal thought content with <internal_thought> and </internal_thought> tags.

An example response might look like:

<internal thought> This is a good opportunity to ask about a due goal</internal thought> What are your thoughts on the upcoming project deadline?"
</formatting>
"""


MAX_MEMORY_LENGTH = 12000  # Characters
