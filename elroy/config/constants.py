import enum
from typing import Any, Callable, Dict, List

MEMORY_WORD_COUNT_LIMIT = 300


# In system persona, the string to replace with the actual user alias
USER_ALIAS_STRING = "$USER_ALIAS"

ASSISTANT_ALIAS_STRING = "$ASSISTANT_ALIAS"

SYSTEM_INSTRUCTION_LABEL = "<system_instruction>"
SYSTEM_INSTRUCTION_LABEL_END = "</system_instruction>"


UNKNOWN = "Unknown"


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

OPENAI_EMBEDDINGS_MODELS = ["text-embedding-ada-002"]


# Empty decorator just meaning to communicate a function should be a tool
def tool(func: Callable) -> Callable:
    setattr(func, "_is_tool", True)
    return func


def allow_unused(func: Callable) -> Callable:
    setattr(func, "_allow_unused", True)
    return func


class MissingAssistantToolCallError(Exception):
    pass


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


FORMATTING_INSTRUCT = """
<formatting>
Include in your response internal thoughts. Indicate internal thought content with <internal_thought> and </internal_thought> tags.

An example response might look like:

<internal thought> THis is a good opportunity to ask about a due goal</internal thought> What are your thoughts on the upcoming project deadline?"
</formatting>
"""


def inline_tool_instruct(schemas: List[Dict[str, Any]]) -> str:
    return (
        "\n".join(["<tool_call_schemas>", *[str(x) for x in schemas], "</tool_call_schemas>"])
        + """
<tool_call_instructions>
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


MAX_MEMORY_LENGTH = 12000  # Characters
