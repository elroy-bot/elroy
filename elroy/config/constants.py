MEMORY_WORD_COUNT_LIMIT = 300

INNER_THOUGHT_TAG = "INNER_THOUGHT_MONOLOGUE"
SYSTEM_INSTRUCTION_LABEL = "*Elroy System Instruction*"

UNKNOWN = "Unknown"

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

# In system persona, the string to replace with the actual user alias
USER_ALIAS_STRING = "$USER_ALIAS"


class MissingAssistantToolCallError(Exception):
    pass


class MissingToolCallMessageError(Exception):
    pass


class MaxRetriesExceededError(Exception):
    pass


class MissingSystemInstructError(Exception):
    pass


class MisplacedSystemInstructError(Exception):
    pass
