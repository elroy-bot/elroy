import os
from datetime import timedelta

INNER_THOUGHT_TAG = "inner_thought_monologue"

UNKNOWN = "Unknown"
MEMORY_TITLE_EXAMPLES = """
Examples of good and bad memory titles are below. Note, the BETTER examples, some titles have been split into two.:

BAD:
- [User Name]'s project progress and personal goals: 'Personal goals' is too vague, and the title describes two different topics.

BETTER:
- [User Name]'s project on building a treehouse: More specific, and describes a single topic.
- [User Name]'s goal to be more thoughtful in conversation: Describes a specific goal.

BAD:
- [User Name]'s weekend plans: 'Weekend plans' is too vague, and dates must be referenced in ISO 8601 format.

BETTER:
- [User Name]'s plan to attend a concert on 2022-02-11: More specific, and includes a specific date.

BAD:
- [User Name]'s preferred name and well being: Two different topics, and 'well being' is too vague.

BETTER:
- [User Name]'s preferred name: Describes a specific topic.
- [User Name]'s feeling of rejuvenation after rest: Describes a specific topic.
"""

CLI_USER_ID = 1

### Model parameters ###

CHAT_MODEL = os.getenv("ELROY_CHAT_MODEL", "gpt-4o")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIZE = 1536

MIN_CONVO_AGE_FOR_GREETING = timedelta(minutes=10)

L2_MEMORY_RELEVANCE_DISTANCE_THRESHOLD = 1.24

L2_MEMORY_CONSOLIDATION_DISTANCE_THRESHOLD = 0.65

INITIAL_REFRESH_WAIT_SECONDS = 30


RESULT_SET_LIMIT_COUNT = 5

MEMORY_WORD_COUNT_LIMIT = 300
DEFAULT_ASSISTANT_COLOR = "#77DFD8"
DEFAULT_INPUT_COLOR = "#FFE377"
DEFAULT_SYSTEM_MESSAGE_COLOR = "#9ACD32"
DEFAULT_WARNING_COLOR = "yellow"
DEFAULT_INTERNAL_THOUGHT_COLOR = "#708090"
