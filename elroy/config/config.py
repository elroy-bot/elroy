import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Generator, Generic, Optional, TypeVar

from litellm import (
    anthropic_models,
    open_ai_chat_completion_models,
    open_ai_embedding_models,
)
from sqlalchemy import NullPool, create_engine
from sqlmodel import Session

from ..io.base import ElroyIO

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class ChatModel:
    model: str
    api_key: Optional[str] = None


@dataclass
class EmbeddingModel:
    model: str
    embedding_size: int
    api_key: Optional[str] = None


@dataclass
class ElroyConfig:
    postgres_url: str
    context_window_token_limit: int
    context_refresh_token_trigger_limit: int  # how many tokens we reach before triggering refresh
    context_refresh_token_target: int  # how many tokens we aim to have after refresh
    max_in_context_message_age_seconds: int  # max age of a message to keep in context
    context_refresh_interval_seconds: int  # how often to refresh system message and compress context messages
    chat_model: ChatModel
    embedding_model: EmbeddingModel


def get_config(
    postgres_url: str,
    chat_model_name: str,
    embedding_model_name: str,
    embedding_model_size: int,
    context_window_token_limit: int,
    openai_api_key: Optional[str],
    anthropic_api_key: Optional[str],
) -> ElroyConfig:

    if chat_model_name in open_ai_chat_completion_models:  # in from litellm import open_ai_chat_completion_models, anthropic_models
        assert openai_api_key is not None, "OpenAI API key is required for OpenAI chat models"
        chat_model = ChatModel(model=chat_model_name, api_key=openai_api_key)
    elif chat_model_name in anthropic_models:
        assert anthropic_api_key is not None, "Anthropic API key is required for Anthropic chat models"
        chat_model = ChatModel(model=chat_model_name, api_key=anthropic_api_key)
    else:
        chat_model = ChatModel(model=chat_model_name)

    if embedding_model_name in open_ai_embedding_models:
        assert openai_api_key is not None, "OpenAI API key is required for OpenAI embedding models"
        embedding_model = EmbeddingModel(model=embedding_model_name, embedding_size=embedding_model_size, api_key=openai_api_key)
    else:
        embedding_model = EmbeddingModel(model=embedding_model_name, embedding_size=embedding_model_size)

    return ElroyConfig(
        postgres_url=postgres_url,
        chat_model=chat_model,
        embedding_model=embedding_model,
        context_window_token_limit=context_window_token_limit,
        context_refresh_token_trigger_limit=int(context_window_token_limit * 0.66),
        context_refresh_token_target=int(context_window_token_limit * 0.33),
        max_in_context_message_age_seconds=int(timedelta(hours=2).total_seconds()),
        context_refresh_interval_seconds=int(timedelta(minutes=10).total_seconds()),
    )


@contextmanager
def session_manager(postgres_url: str) -> Generator[Session, None, None]:
    engine = create_engine(postgres_url, poolclass=NullPool)
    session = Session(engine)
    try:
        yield session
        if session.is_active:  # Only commit if the session is still active
            session.commit()
    except Exception:
        if session.is_active:  # Only rollback if the session is still active
            session.rollback()
        raise
    finally:
        if session.is_active:  # Only close if not already closed
            session.close()


T = TypeVar("T", bound=ElroyIO)


@dataclass
class ElroyContext(Generic[T]):
    session: Session
    io: T
    config: ElroyConfig
    user_id: int
