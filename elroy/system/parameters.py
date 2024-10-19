import os

CLI_USER_ID = 1

### Model parameters ###

CHAT_MODEL = os.getenv("ELROY_CHAT_MODEL", "gpt-4o")
MEMORY_PROCESSING_MODEL = os.getenv("MEMORY_PROCESSING_MODEL", "gpt-4o-mini")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIZE = 1536
L2_RANDOM_WORD_DISTANCE = 1.38  # Absolute value of L2 distance between a memory and a random nonsense sentence. Useful for baseline.
L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD = (
    10  # Threshold for how much closer a query should be to a memory than a random sentence to be considered relevant.
)
RESULT_SET_LIMIT_COUNT = 5

# String constants

UNKNOWN = "Unknown"

INNER_THOUGHT_TAG = "inner_thought_monologue"
