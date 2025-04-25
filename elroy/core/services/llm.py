"""
LLM service for ElroyContext.
"""

from functools import cached_property

from ...config.llm import (
    ChatModel,
    EmbeddingModel,
    get_chat_model,
    get_embedding_model,
    infer_chat_model_name,
)


class LLMService:
    """Provides access to LLM models with lazy initialization"""

    def __init__(self, config):
        self.config = config

    @property
    def is_chat_model_inferred(self) -> bool:
        return self.config.chat_model is None

    @cached_property
    def chat_model(self) -> ChatModel:
        if not self.config.chat_model:
            chat_model_name = infer_chat_model_name()
        else:
            chat_model_name = self.config.chat_model

        return get_chat_model(
            model_name=chat_model_name,
            openai_api_key=self.config.openai_api_key,
            openai_api_base=self.config.openai_api_base,
            api_key=self.config.chat_model_api_key,
            api_base=self.config.chat_model_api_base,
            enable_caching=self.config.enable_caching,
            inline_tool_calls=self.config.inline_tool_calls,
        )

    @cached_property
    def embedding_model(self) -> EmbeddingModel:
        return get_embedding_model(
            model_name=self.config.embedding_model,
            embedding_size=self.config.embedding_model_size,
            api_key=self.config.embedding_model_api_key,
            api_base=self.config.embedding_model_api_base,
            openai_embedding_api_base=self.config.openai_embedding_api_base,
            openai_api_key=self.config.openai_api_key,
            openai_api_base=self.config.openai_api_base,
            enable_caching=self.config.enable_caching,
        )
