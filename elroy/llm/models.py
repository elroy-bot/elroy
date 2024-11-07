from enum import Enum

class ChatModel(Enum):
    GPT4_TURBO = "gpt-4-1106-preview"  # Latest GPT-4 model
    GPT4 = "gpt-4"                     # Base GPT-4 model
    GPT35_TURBO = "gpt-3.5-turbo"      # GPT-3.5 model
    CLAUDE_SONNET = "claude-3-sonnet"   # Claude 3 Sonnet model
    CLAUDE_HAIKU = "claude-3-haiku"     # Claude 3 Haiku model

class EmbeddingModel(Enum):
    ADA = "text-embedding-ada-002"
