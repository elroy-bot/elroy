from enum import Enum

class ChatModel(Enum):
    GPT4 = "gpt-4-1106-preview"  # For complex reasoning tasks
    GPT35 = "gpt-3.5-turbo"      # For simpler tasks

class EmbeddingModel(Enum):
    ADA = "text-embedding-ada-002"
