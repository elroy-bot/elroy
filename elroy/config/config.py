import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Generator, Generic, Optional, TypeVar

import typer
import yaml
from sqlalchemy import NullPool, create_engine
from sqlmodel import Session

from ..io.base import ElroyIO
from .constants import LIST_MODELS_FLAG

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS_CONFIG_PATH = os.path.join(ROOT_DIR, "config", "defaults.yml")

with open(DEFAULTS_CONFIG_PATH, "r") as default_config_file:
    DEFAULT_CONFIG = yaml.safe_load(default_config_file)


@lru_cache
def load_defaults(user_config_path: Optional[str] = None) -> dict:
    """
    Load configuration values in order of precedence:
    1. defaults.yml (base defaults)
    2. User config file (if provided)
    """
    with open(DEFAULTS_CONFIG_PATH, "r") as default_config_file:
        config = yaml.safe_load(default_config_file)

    if user_config_path:
        if not Path(user_config_path).exists():
            logging.error(f"User config file {user_config_path} not found, using default values")
        elif not Path(user_config_path).is_file():
            logging.error(f"User config path {user_config_path} is not a file, using default values")
        else:
            try:
                with open(user_config_path, "r") as user_config_file:
                    user_config = yaml.safe_load(user_config_file)
                config.update(user_config)
            except Exception as e:
                logging.error(f"Failed to load user config file {user_config_path}: {e}")
    return config


@dataclass
class ChatModel:
    model: str
    enable_caching: bool
    api_key: Optional[str]
    ensure_alternating_roles: (
        bool  # Whether to ensure that the first message is system message, and thereafter alternating between user and assistant.
    )
    api_base: Optional[str] = None
    organization: Optional[str] = None


@dataclass
class EmbeddingModel:
    model: str
    embedding_size: int
    enable_caching: bool
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    organization: Optional[str] = None


@dataclass
class ElroyConfig:
    postgres_url: str
    context_refresh_token_trigger_limit: int  # how many tokens we reach before triggering refresh
    context_refresh_token_target: int  # how many tokens we aim to have after refresh
    max_in_context_message_age: timedelta  # max age of a message to keep in context
    context_refresh_interval: timedelta  # how often to refresh system message and compress context messages
    min_convo_age_for_greeting: timedelta  # minimum age of conversation before showing greeting
    l2_memory_relevance_distance_threshold: float  # threshold for memory relevance
    l2_memory_consolidation_distance_threshold: float  # threshold for memory consolidation
    initial_refresh_wait: timedelta  # initial wait time before first refresh
    chat_model: ChatModel
    embedding_model: EmbeddingModel
    debug_mode: bool  # Whether to emit more verbose logging and fail faster on errors rather than attempting to recover
    log_file_path: str


def get_config(
    postgres_url: str,
    chat_model_name: str,
    embedding_model: str,
    embedding_model_size: int,
    context_refresh_trigger_tokens: int,
    context_refresh_target_tokens: int,
    max_context_age_minutes: float,
    context_refresh_interval_minutes: float,
    min_convo_age_for_greeting_minutes: float,
    l2_memory_relevance_distance_threshold: float,
    l2_memory_consolidation_distance_threshold: float,
    initial_context_refresh_wait_seconds: int,
    debug: bool,
    openai_api_key: Optional[str],
    anthropic_api_key: Optional[str],
    openai_api_base: Optional[str],
    openai_embedding_api_base: Optional[str],
    openai_organization: Optional[str],
    log_file_path: str,
    enable_caching: bool,
) -> ElroyConfig:
    from litellm import (
        anthropic_models,
        open_ai_chat_completion_models,
        open_ai_embedding_models,
    )

    if not (openai_api_base is not None or chat_model_name in anthropic_models or chat_model_name in open_ai_chat_completion_models):
        raise typer.BadParameter(
            f"Chat model {chat_model_name} not recognized. Please either specify a custom open_api_base, or select a chat model from the list provided by: elroy {LIST_MODELS_FLAG}"
        )

    if chat_model_name in anthropic_models:
        assert anthropic_api_key is not None, "Anthropic API key is required for Anthropic chat models"
        chat_model = ChatModel(
            model=chat_model_name, api_key=anthropic_api_key, ensure_alternating_roles=True, enable_caching=enable_caching
        )
    else:
        if chat_model_name in open_ai_chat_completion_models:
            assert openai_api_key is not None, "OpenAI API key is required for OpenAI chat models"
        chat_model = ChatModel(
            model=chat_model_name,
            api_key=openai_api_key,
            ensure_alternating_roles=False,
            api_base=openai_api_base,
            organization=openai_organization,
            enable_caching=enable_caching,
        )
    if embedding_model in open_ai_embedding_models:
        assert openai_api_key is not None, "OpenAI API key is required for OpenAI embedding models"

    embedding_model_data = EmbeddingModel(
        model=embedding_model,
        embedding_size=embedding_model_size,
        api_key=openai_api_key,
        api_base=openai_embedding_api_base,
        organization=openai_organization,
        enable_caching=enable_caching,
    )

    return ElroyConfig(
        postgres_url=postgres_url,
        chat_model=chat_model,
        embedding_model=embedding_model_data,
        debug_mode=debug,
        context_refresh_token_trigger_limit=context_refresh_trigger_tokens,
        context_refresh_token_target=context_refresh_target_tokens,
        max_in_context_message_age=timedelta(minutes=max_context_age_minutes),
        context_refresh_interval=timedelta(minutes=context_refresh_interval_minutes),
        min_convo_age_for_greeting=timedelta(minutes=min_convo_age_for_greeting_minutes),
        l2_memory_relevance_distance_threshold=l2_memory_relevance_distance_threshold,
        l2_memory_consolidation_distance_threshold=l2_memory_consolidation_distance_threshold,
        initial_refresh_wait=timedelta(seconds=initial_context_refresh_wait_seconds),
        log_file_path=log_file_path,
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
