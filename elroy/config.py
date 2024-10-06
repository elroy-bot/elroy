import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import configargparse
from sqlalchemy import Engine, NullPool, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlmodel import Session
from toolz import assoc, pipe
from toolz.curried import valfilter

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


def str_to_bool(input: Optional[str]) -> bool:
    return input is not None and input.lower() in ["true", "1"]


def get_config() -> ElroyConfig:
    parser = configargparse.ArgParser(default_config_files=["/etc/elroy/config.ini", "~/.elroy.ini"])
    parser.add_argument("--config", is_config_file=True, help="config file path")
    parser.add_argument("--database_url", env_var="ELROY_DATABASE_URL", required=True, help="Database URL")
    parser.add_argument("--openai_api_key", env_var="OPENAI_API_KEY", required=True, help="OpenAI API Key")
    parser.add_argument("--local_storage_path", env_var="ELROY_LOCAL_STORAGE_PATH", default=".cache", help="Local storage path")
    parser.add_argument(
        "--context_window_token_limit",
        env_var="ELROY_CONTEXT_WINDOW_TOKEN_LIMIT",
        type=int,
        default=16384,
        help="Context window token limit",
    )

    args = parser.parse_args()

    config = pipe(
        vars(args),
        valfilter(lambda x: x is not None),
        lambda x: assoc(x, "engine", create_engine(x["database_url"], poolclass=NullPool)),
        lambda x: assoc(x, "declarative_base", declarative_base()),
        lambda x: assoc(x, "session_maker", sessionmaker(bind=x["engine"])),
        lambda x: assoc(x, "context_refresh_token_trigger_limit", int(x["context_window_token_limit"] * 0.66)),
        lambda x: assoc(x, "context_refresh_token_target", int(x["context_window_token_limit"] * 0.33)),
        lambda x: ElroyConfig(**x),
    )
    assert isinstance(config, ElroyConfig)

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
