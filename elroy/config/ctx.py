import sys
from contextlib import contextmanager
from datetime import timedelta
from functools import cached_property, wraps
from typing import Any, Callable, Generator, Optional, TypeVar, Union

import click
import typer

from ..db.db_manager import DbManager
from ..db.postgres.postgres_manager import PostgresManager
from ..db.sqlite.sqlite_manager import SqliteManager
from ..repository.user import create_user_id, get_user_id_if_exists
from .config import ChatModel, EmbeddingModel, get_chat_model, get_embedding_model


class ElroyContext(typer.Context):
    from ..io.base import ElroyIO
    from ..io.cli import CliIO

    _db: Optional[DbManager] = None
    _io: Optional[ElroyIO] = None

    def __init__(
        self,
        command: click.Command,
        *,
        # Required attributes
        config_file: str,
        database_url: str,
        show_internal_thought: bool,
        system_message_color: str,
        assistant_color: str,
        user_input_color: str,
        warning_color: str,
        internal_thought_color: str,
        user_token: str,
        # API Configuration
        openai_api_key: Optional[str] = None,
        openai_api_base: Optional[str] = None,
        openai_embedding_api_base: Optional[str] = None,
        openai_organization: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        enable_tools: bool,
        # Model Configuration
        chat_model: str,
        embedding_model: str,
        embedding_model_size: int,
        enable_caching: bool = True,
        # Context Management
        context_refresh_trigger_tokens: int,
        context_refresh_target_tokens: int,
        max_context_age_minutes: float,
        context_refresh_interval_minutes: float,
        min_convo_age_for_greeting_minutes: float,
        enable_assistant_greeting: bool,
        initial_context_refresh_wait_seconds: int,
        # Memory Management
        l2_memory_relevance_distance_threshold: float,
        l2_memory_consolidation_distance_threshold: float,
        # Basic Configuration
        debug: bool,
        log_file_path: str,
        default_persona: str,
        default_assistant_name: str,
        tool: Optional[str],
        # Typer context params
        parent: Optional[typer.Context] = None,
        **kwargs,
    ):
        super().__init__(command, parent=parent, **kwargs)
        # Store all constructor params
        self.config_file = config_file
        self.database_url = database_url
        self.show_internal_thought = show_internal_thought
        self.system_message_color = system_message_color
        self.assistant_color = assistant_color
        self.user_input_color = user_input_color
        self.warning_color = warning_color
        self.internal_thought_color = internal_thought_color
        self.user_token = user_token

        # API Configuration
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.openai_embedding_api_base = openai_embedding_api_base
        self.openai_organization = openai_organization
        self.anthropic_api_key = anthropic_api_key

        # Model Configuration
        self.chat_model_name = chat_model
        self.embedding_model_name = embedding_model
        self.embedding_model_size = embedding_model_size
        self.enable_caching = enable_caching
        self.enable_tools = enable_tools

        # Context Management
        self.context_refresh_trigger_tokens = context_refresh_trigger_tokens
        self.context_refresh_target_tokens = context_refresh_target_tokens
        self.max_context_age_minutes = max_context_age_minutes
        self.context_refresh_interval_minutes = context_refresh_interval_minutes
        self.min_convo_age_for_greeting_minutes = min_convo_age_for_greeting_minutes
        self.enable_assistant_greeting = enable_assistant_greeting
        self.max_in_context_message_age = timedelta(minutes=max_context_age_minutes)
        self.initial_refresh_wait = timedelta(seconds=initial_context_refresh_wait_seconds)
        self.context_refresh_interval = timedelta(minutes=context_refresh_interval_minutes)

        # Memory Management
        self.l2_memory_relevance_distance_threshold = l2_memory_relevance_distance_threshold
        self.l2_memory_consolidation_distance_threshold = l2_memory_consolidation_distance_threshold
        self.initial_context_refresh_wait_seconds = initial_context_refresh_wait_seconds

        # Basic Configuration
        self.debug = debug
        self.log_file_path = log_file_path
        self.default_persona = default_persona
        self.default_assistant_name = default_assistant_name

        self.tool = tool

    @property
    def min_convo_age_for_greeting(self) -> timedelta:
        return timedelta(minutes=self.min_convo_age_for_greeting_minutes)

    @cached_property
    def chat_model(self) -> ChatModel:
        return get_chat_model(
            model_name=self.chat_model_name,
            openai_api_key=self.openai_api_key,
            anthropic_api_key=self.anthropic_api_key,
            api_base=self.openai_api_base,
            organization=self.openai_organization,
            enable_caching=self.enable_caching,
        )

    @cached_property
    def embedding_model(self) -> EmbeddingModel:
        return get_embedding_model(
            model_name=self.embedding_model_name,
            embedding_size=self.embedding_model_size,
            api_key=self.openai_api_key,
            api_base=self.openai_api_base,
            organization=self.openai_organization,
            enable_caching=self.enable_caching,
        )

    @cached_property
    def is_new_user(self) -> bool:
        # This will be set when user_id property is accessed
        if not hasattr(self, "_is_new_user"):
            raise ValueError("Cannot determine if new user created, fetch user id first")
        return self._is_new_user

    @cached_property
    def user_id(self) -> int:
        stored_user_id = get_user_id_if_exists(self.db, self.user_token)

        if stored_user_id:
            self._is_new_user = False
            self._user_id = stored_user_id
        else:
            self._user_id = create_user_id(self.db, self.user_token)
            self._is_new_user = True
        return self._user_id

    @property
    def io(self) -> ElroyIO:
        from ..io.base import StdIO

        if not self._io:
            if sys.stdin.isatty():
                from ..io.cli import CliIO

                self._io = CliIO(
                    show_internal_thought=self.show_internal_thought,
                    system_message_color=self.system_message_color,
                    assistant_message_color=self.assistant_color,
                    user_input_color=self.user_input_color,
                    warning_color=self.warning_color,
                    internal_thought_color=self.internal_thought_color,
                )

            else:
                self._io = StdIO()

        return self._io

    @property
    def db(self) -> DbManager:
        if not self._db:
            raise ValueError("No db session open")
        else:
            return self._db

    @contextmanager
    def with_db(self, db: DbManager) -> Generator[None, None, None]:
        """Context manager for database sessions"""
        try:
            self._db = db
            yield
        finally:
            self._db = None


def get_ctx(typer_ctx: Union[typer.Context, ElroyContext]) -> ElroyContext:
    if isinstance(typer_ctx, ElroyContext):
        return typer_ctx

    ctx = typer_ctx.obj
    assert isinstance(ctx, ElroyContext)
    return ctx


T = TypeVar("T", bound=Callable[..., Any])


def elroy_context(func: T) -> T:
    """
    Decorator that converts a typer.Context argument to ElroyContext.
    Expects first argument to be the context.
    """

    @wraps(func)
    def wrapper(ctx, *args, **kwargs):
        if not isinstance(ctx, ElroyContext):
            ctx = ctx.obj
        assert isinstance(ctx, ElroyContext), f"Context must be ElroyContext, got {type(ctx)}"
        return func(ctx, *args, **kwargs)

    return wrapper  # type: ignore


def clone_ctx_with_db(ctx: ElroyContext, db: DbManager) -> ElroyContext:

    new_ctx = ElroyContext(
        command=ctx.command,
        parent=ctx.parent,  # type: ignore
        config_file=ctx.config_file,
        database_url=ctx.database_url,
        show_internal_thought=ctx.show_internal_thought,
        system_message_color=ctx.system_message_color,
        assistant_color=ctx.assistant_color,
        user_input_color=ctx.user_input_color,
        warning_color=ctx.warning_color,
        internal_thought_color=ctx.internal_thought_color,
        user_token=ctx.user_token,
        openai_api_key=ctx.openai_api_key,
        openai_api_base=ctx.openai_api_base,
        openai_embedding_api_base=ctx.openai_embedding_api_base,
        openai_organization=ctx.openai_organization,
        anthropic_api_key=ctx.anthropic_api_key,
        chat_model=ctx.chat_model_name,
        embedding_model=ctx.embedding_model_name,
        embedding_model_size=ctx.embedding_model_size,
        enable_caching=ctx.enable_caching,
        context_refresh_trigger_tokens=ctx.context_refresh_trigger_tokens,
        context_refresh_target_tokens=ctx.context_refresh_target_tokens,
        max_context_age_minutes=ctx.max_context_age_minutes,
        context_refresh_interval_minutes=ctx.context_refresh_interval_minutes,
        min_convo_age_for_greeting_minutes=ctx.min_convo_age_for_greeting_minutes,
        enable_assistant_greeting=ctx.enable_assistant_greeting,
        initial_context_refresh_wait_seconds=ctx.initial_context_refresh_wait_seconds,
        l2_memory_relevance_distance_threshold=ctx.l2_memory_relevance_distance_threshold,
        l2_memory_consolidation_distance_threshold=ctx.l2_memory_consolidation_distance_threshold,
        debug=ctx.debug,
        log_file_path=ctx.log_file_path,
        default_persona=ctx.default_persona,
        default_assistant_name=ctx.default_assistant_name,
        tool=ctx.tool,
        enable_tools=ctx.enable_tools,
    )
    new_ctx._db = db
    return new_ctx


def with_db(func):
    """Decorator that provides database connection to ElroyContext methods"""
    from functools import wraps

    @wraps(func)
    def wrapper(ctx: ElroyContext, *args, **kwargs):

        if ctx.database_url.startswith("postgresql://"):
            db_manager = PostgresManager
        elif ctx.database_url.startswith("sqlite:///"):
            db_manager = SqliteManager
        else:
            raise ValueError(f"Unsupported database URL: {ctx.database_url}. Must be either a postgresql:// or sqlite:/// URL")

        with db_manager.open_session(ctx.database_url, True) as db:
            with ctx.with_db(db):
                return func(ctx, *args, **kwargs)

    return wrapper
