import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from rich.console import Console
from sqlalchemy import NullPool, create_engine
from sqlmodel import Session
from contextlib import contextmanager
from typing import Generator


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))




@dataclass
class ElroyConfig:
    postgres_url: str
    openai_api_key: str
    context_window_token_limit: int
    context_refresh_token_trigger_limit: int  # how many tokens we reach before triggering refresh
    context_refresh_token_target: int  # how many tokens we aim to have after refresh
    max_in_context_message_age_seconds: int  # max age of a message to keep in context
    context_refresh_interval_seconds: int  # how often to refresh system message and compress context messages


def get_config(
    postgres_url: str,
    openai_api_key: str,
    context_window_token_limit: Optional[int] = None,
) -> ElroyConfig:
    context_window_token_limit = context_window_token_limit or 16384

    return ElroyConfig(
        postgres_url=postgres_url,
        openai_api_key=openai_api_key,
        context_window_token_limit=context_window_token_limit,
        context_refresh_token_trigger_limit=int(context_window_token_limit * 0.66),
        context_refresh_token_target=int(context_window_token_limit * 0.33),
        max_in_context_message_age_seconds=int(timedelta(hours=2).total_seconds()),
        context_refresh_interval_seconds=int(timedelta(minutes=30).total_seconds()),
    )




@contextmanager
def session_manager(postgres_url: str) -> Generator[Session, None, None]:
    session = Session(create_engine(postgres_url, poolclass=NullPool))
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()



@dataclass
class ElroyContext:
    session: Session
    console: Console
    config: ElroyConfig
    user_id: int
