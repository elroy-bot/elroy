import enum
from typing import Callable, Dict, List

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

# In future, consider making this param dynamic
EMBEDDING_SIZE = 1536


RESULT_SET_LIMIT_COUNT = 5

REPO_ISSUES_URL = "https://github.com/elroy-bot/elroy/issues"

BUG_REPORT_LOG_LINES = 15


MODEL_SELECTION_CONFIG_PANEL = "Model Selection and Configuration"

EXIT = "exit"

IS_TOOL = "_is_tool"
IS_ENABLED = "_is_enabled"
IS_USER_ONLY_TOOL = "_is_user_only_tool"


# Empty decorator just meaning to communicate a function should be a tool
def tool(func: Callable) -> Callable:
    from .tracing import tracer

    setattr(func, IS_TOOL, True)
    return tracer.tool(func)


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


class RecoverableToolError(Exception):
    """Exceptions in tool calls that the assistant can learn from and correct"""


class Provider(enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    AZURE = "azure"
    OTHER = "other"


ELROY_DATABASE_URL = "ELROY_DATABASE_URL"

GEMINI_PREFIX = "gemini"
AZURE_PREFIX = "azure"

CLAUDE_3_5_SONNET = "claude-sonnet-4-5-20250929"  # Updated to Claude 4.5 Sonnet
GPT_5 = "gpt-5"
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
        GPT_5,
        "gpt-5-mini",
        "gpt-5-nano",
        TEXT_EMBEDDING_3_SMALL,
        "text-embedding-3-large,",
    ],
    Provider.ANTHROPIC: [
        CLAUDE_3_5_SONNET,
        # Claude 4.5 models
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-5-20251101",
        # Claude 3.5 models (older, may be deprecated)
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-haiku-20241022",
        # Claude 3 models
        "claude-3",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        # Claude 2 models
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

<internal thought> This is a good opportunity to ask about a due reminder</internal thought> What are your thoughts on the upcoming project deadline?"
</formatting>
"""


MAX_MEMORY_LENGTH = 12000  # Characters
