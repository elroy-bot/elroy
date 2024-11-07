from enum import Enum

from litellm.models import AnthropicModels, OpenAIModels


class ChatModel(Enum):
    GPT4_TURBO = OpenAIModels.GPT4_TURBO_PREVIEW  # Latest GPT-4 model
    GPT4 = OpenAIModels.GPT4  # Base GPT-4 model
    GPT35_TURBO = OpenAIModels.GPT35_TURBO  # GPT-3.5 model
    CLAUDE_SONNET = AnthropicModels.CLAUDE_3_SONNET  # Claude 3 Sonnet model
    CLAUDE_HAIKU = AnthropicModels.CLAUDE_3_HAIKU  # Claude 3 Haiku model


class EmbeddingModel(Enum):
    ADA = OpenAIModels.ADA_EMBEDDING_V2  # text-embedding-ada-002
