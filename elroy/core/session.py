import inspect
import uuid
from contextlib import contextmanager
from typing import TypeVar

from ..io.base import ElroyIO
from .ctx import ElroyConfig
from .db import get_db_manager
from .logging import get_logger
from .session_bootstrap import bootstrap_turn
from .turn import ElroySession, TurnContext

logger = get_logger()
T = TypeVar("T")


def clone_config(config: ElroyConfig) -> ElroyConfig:
    cloned = type(config)(
        database_url=config.database_url,
        chroma_path=config.chroma_path,
        model_config=config.model_config,
        ui_config=config.ui_config,
        memory_config=config.memory_config,
        tool_config=config.tool_config,
        runtime_config=config.runtime_config,
    )
    for attr in ("chat_model", "fast_model", "embedding_model", "llm", "fast_llm", "tool_registry", "latency_tracker"):
        if attr in config.__dict__:
            cloned.__dict__[attr] = config.__dict__[attr]
    return cloned


@contextmanager
def init_elroy_session(config: ElroyConfig, io: ElroyIO | None, check_db_migration: bool, should_onboard_interactive: bool):
    _ = (io, should_onboard_interactive)
    from ..repository.user.store import UserStore

    db_manager = get_db_manager(config)
    if check_db_migration:
        db_manager.check_connection()
        db_manager.migrate_if_needed()

    session_id = str(uuid.uuid4())
    logger.debug(f"OpenTelemetry instrumentation enabled with session ID: {session_id}")

    with db_manager.open_session() as db:
        user_exists = UserStore(db).get_user_id_if_exists(config.user_token) is not None

    session = build_elroy_session(config, db_manager=db_manager)
    with open_turn_context(config, session) as turn:
        bootstrap_turn(turn, user_exists=user_exists)
        yield session


def build_elroy_session(config: ElroyConfig, *, db_manager=None) -> ElroySession:
    from ..repository.user.store import UserStore

    db_manager = db_manager or get_db_manager(config)
    with db_manager.open_session() as db:
        user_id = UserStore(db).get_or_create_user_id(config.runtime_config.user_token)

    return ElroySession(
        db_manager=db_manager,
        user_id=user_id,
        user_token=config.runtime_config.user_token,
    )


@contextmanager
def open_turn_context(config: ElroyConfig, session: ElroySession | None = None):
    session = session or build_elroy_session(config)
    with session.db_manager.open_session() as db:
        yield TurnContext(
            config=config,
            session=session,
            db=db,
        )


def run_with_turn(
    config: ElroyConfig,
    fn,
    /,
    *args,
    session: ElroySession | None = None,
    **kwargs,
) -> T:
    session = session or build_elroy_session(config)
    with open_turn_context(config, session) as turn:
        return fn(turn, *args, **kwargs)


def invoke_with_config(func, config: ElroyConfig, /, *args, **kwargs):
    return invoke_with_session(func, config, build_elroy_session(config), *args, **kwargs)


def invoke_with_session(func, config: ElroyConfig, session: ElroySession, /, *args, **kwargs):
    """Invoke a function that may request ElroyConfig or TurnContext."""

    signature = inspect.signature(func)
    turn_param_name = next((name for name, param in signature.parameters.items() if param.annotation == TurnContext), None)
    config_param_name = next((name for name, param in signature.parameters.items() if param.annotation == ElroyConfig), None)

    if turn_param_name is not None:
        with open_turn_context(config, session) as turn:
            return func(*args, **{**kwargs, turn_param_name: turn})

    if config_param_name is not None and config_param_name not in kwargs:
        kwargs = {**kwargs, config_param_name: config}

    return func(*args, **kwargs)
