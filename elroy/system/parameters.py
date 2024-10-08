import os
from datetime import timedelta

CLI_USER_ID = 1

### Model parameters ###

CHAT_MODEL = os.getenv("ELROY_CHAT_MODEL", "gpt-4o")
MEMORY_PROCESSING_MODEL = os.getenv("MEMORY_PROCESSING_MODEL", "gpt-4o-mini")

CACHE_LENGTH_RANDOMIZATION_FACTOR = 0.15

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIZE = 1536
L2_RANDOM_WORD_DISTANCE = 1.38  # Absolute value of L2 distance between a memory and a random nonsense sentence. Useful for baseline.
L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD = (
    10  # Threshold for how much closer a query should be to a memory than a random sentence to be considered relevant.
)
RESULT_SET_LIMIT_COUNT = 5


MESSAGE_LENGTH_WORDS_GUIDANCE = 300

# for for low temp llm prompts
LOW_TEMPERATURE = 0.2

### Context refresh parameters ###

# Time threshold to wait until refreshing the context window
WATERMARK_INVALIDATION_SECONDS = timedelta(minutes=3).total_seconds()
# Max message age to keep within context window during context refresh
MAX_IN_CONTEXT_MESSAGE_AGE_SECONDS = timedelta(hours=2).total_seconds()

### Feature rollouts ###

GOAL_CHECKIN_COUNT = 4

# String constants

UNKNOWN = "Unknown"

INNER_THOUGHT_TAG = "inner_thought_monologue"
