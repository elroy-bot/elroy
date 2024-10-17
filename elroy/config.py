import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from rich.console import Console
from sqlalchemy import Engine, NullPool, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlmodel import Session
from toolz import assoc, pipe
from toolz.curried import valfilter

from elroy.logging_config import setup_logging

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ElroyEnv(Enum):
    TESTING = "testing"
    LOCAL = "local"


@dataclass
class ElroyConfig:
    database_url: str
    openai_api_key: str
    local_storage_path: Optional[str]
    engine: Engine
    declarative_base: Any
    context_window_token_limit: int
    context_refresh_token_trigger_limit: int  # how many tokens we reach before triggering refresh
    context_refresh_token_target: int  # how many tokens we aim to have after refresh
    session_maker: sessionmaker[Session]
    log_file_path: str


def str_to_bool(input: Optional[str]) -> bool:
    return input is not None and input.lower() in ["true", "1"]


def get_config() -> ElroyConfig:
    database_url = os.environ.get("ELROY_DATABASE_URL")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    local_storage_path = os.environ.get("ELROY_LOCAL_STORAGE_PATH", ".cache")
    context_window_token_limit = int(os.environ.get("ELROY_CONTEXT_WINDOW_TOKEN_LIMIT", "16384"))
    log_file_path = os.environ.get("ELROY_LOG_FILE_PATH", os.path.join(ROOT_DIR, "logs", "elroy.log"))

    if not database_url:
        raise ValueError("ELROY_DATABASE_URL environment variable is not set")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    config = pipe(
        {
            "database_url": database_url,
            "openai_api_key": openai_api_key,
            "local_storage_path": local_storage_path,
            "context_window_token_limit": context_window_token_limit,
            "log_file_path": log_file_path,
        },
        valfilter(lambda x: x is not None),
        lambda x: assoc(x, "engine", create_engine(x["database_url"], poolclass=NullPool)),
        lambda x: assoc(x, "declarative_base", declarative_base()),
        lambda x: assoc(x, "session_maker", sessionmaker(bind=x["engine"])),
        lambda x: assoc(x, "context_refresh_token_trigger_limit", int(x["context_window_token_limit"] * 0.66)),
        lambda x: assoc(x, "context_refresh_token_target", int(x["context_window_token_limit"] * 0.33)),
        lambda x: ElroyConfig(**x),
    )
    assert isinstance(config, ElroyConfig)

    # Set up logging
    setup_logging(config.log_file_path)

    return config


from contextlib import contextmanager
from typing import Generator


@contextmanager
def session_manager() -> Generator[Session, None, None]:
    session = Session(get_config().engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_elroy_env() -> ElroyEnv:
    if os.environ.get("PYTEST_VERSION"):
        return ElroyEnv.TESTING
    else:
        return ElroyEnv.LOCAL


is_test_env = lambda: _get_elroy_env() == ElroyEnv.TESTING


@dataclass
class ElroyContext:
    session: Session
    console: Console
    config: ElroyConfig
    user_id: int
