import enum
from typing import Dict, List

MEMORY_WORD_COUNT_LIMIT = 300

DEFAULT_USER_TOKEN = "DEFAULT"

INNER_THOUGHT_TAG = "INNER_THOUGHT_MONOLOGUE"

# In system persona, the string to replace with the actual user alias
USER_ALIAS_STRING = "$USER_ALIAS"

ASSISTANT_ALIAS_STRING = "$ASSISTANT_ALIAS"

SYSTEM_INSTRUCTION_LABEL = "*System Instruction*"


UNKNOWN = "Unknown"

AUTO = "auto"

# Message roles
USER, ASSISTANT, TOOL, SYSTEM = ["user", "assistant", "tool", "system"]

CLI_USER_ID = 1

### Model parameters ###

# TODO: make this dynamic
EMBEDDING_SIZE = 1536


RESULT_SET_LIMIT_COUNT = 5

REPO_ISSUES_URL = "https://github.com/elroy-bot/elroy/issues"

BUG_REPORT_LOG_LINES = 15

LIST_MODELS_FLAG = "--list-models"

MODEL_SELECTION_CONFIG_PANEL = "Model Selection and Configuration"

MAX_CHAT_COMPLETION_RETRY_COUNT = 2

CONFIG_FILE_KEY = "config_file"


class MissingAssistantToolCallError(Exception):
    pass


class MissingToolCallMessageError(Exception):
    pass


class InvalidForceToolError(Exception):
    pass


class MaxRetriesExceededError(Exception):
    pass


class MissingSystemInstructError(Exception):
    pass


class MisplacedSystemInstructError(Exception):
    pass


class Provider(enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OTHER = "other"


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
        "gpt-4o",
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
    ],
    Provider.ANTHROPIC: [
        "claude-3-opus-20240229",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-sonnet-20240229",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307",
        "claude-2.1",
        "claude-2",
        "claude-instant-1.2",
        "claude-instant-1",
    ],
}
