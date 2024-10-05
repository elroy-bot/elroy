import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import Engine, NullPool, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlmodel import Session
from toolz import assoc, pipe
from toolz.curried import merge, valfilter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ElroyEnv(Enum):
    TESTING = "testing"
    LOCAL = "local"
    DOCKER_LOCAL = "docker_local"


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

    env = _get_elroy_env()

    if env == ElroyEnv.TESTING:
        params = _load_testing_config()
    elif env == ElroyEnv.LOCAL:
        params = _load_local_config()
    elif env == ElroyEnv.DOCKER_LOCAL:
        params = _load_docker_local()
    else:
        raise ValueError(f"Unknown environment: {env}")

    # merge env specific vars, priority to env vars
    env_variables = valfilter(
        lambda x: x is not None,
        {
            "database_url": os.environ.get("ELROY_DATABASE_URL"),
            "context_window_token_limit": (
                int(os.environ["ELROY_CONTEXT_WINDOW_TOKEN_LIMIT"]) if os.environ.get("ELROY_CONTEXT_WINDOW_TOKEN_LIMIT") else None
            ),
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "local_storage_path": os.environ.get("ELROY_LOCAL_STORAGE_PATH"),
        },
    )

    config = pipe(
        params,
        valfilter(lambda x: x is not None),
        lambda x: merge(x, env_variables),  # env specific configs are priority
        lambda x: assoc(x, "engine", create_engine(x["database_url"], poolclass=NullPool)),
        lambda x: assoc(x, "declarative_base", declarative_base()),
        lambda x: assoc(x, "session_maker", sessionmaker(bind=x["engine"])),
        lambda x: assoc(x, "context_refresh_token_trigger_limit", int(x["context_window_token_limit"] * 0.66)),
        lambda x: assoc(x, "context_refresh_token_target", int(x["context_window_token_limit"] * 0.33)),
        lambda x: ElroyConfig(**x),
    )
    assert isinstance(config, ElroyConfig)

    return config


def _load_testing_config() -> Dict:
    load_dotenv(dotenv_path=os.path.join(ROOT_DIR, "tests", ".env"), override=True)
    return {
        "local_storage_path": os.path.join(os.getcwd(), ".cache", "test"),
        "context_window_token_limit": 1000,
    }


def _load_local_config() -> Dict:
    load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env"), override=True)
    return {
        "local_storage_path": os.getenv("LOCAL_STORAGE_PATH", ".cache"),
        "context_window_token_limit": 16384,
    }


def _load_docker_local() -> Dict:
    return {
        "local_storage_path": os.getenv("LOCAL_STORAGE_PATH", ".cache"),
        "context_window_token_limit": 16384,
    }


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
    elif os.environ.get("DOCKER_LOCAL"):
        return ElroyEnv.DOCKER_LOCAL
    else:
        return ElroyEnv.LOCAL


is_test_env = lambda: _get_elroy_env() == ElroyEnv.TESTING
