from enum import Enum

class ChatModel(Enum):
    GPT4O = "gpt-4o"                     # Base GPT-4 model
    GPT35_TURBO = "gpt-3.5-turbo"      # GPT-3.5 model
    SONNET = "claude-3-sonnet"   # Claude 3 Sonnet model
    HAIKU = "claude-3-haiku"     # Claude 3 Haiku model

class EmbeddingModel(Enum):
    ADA = "text-embedding-ada-002"
