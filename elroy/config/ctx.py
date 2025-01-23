from contextlib import contextmanager
from datetime import timedelta
from functools import cached_property
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Generator, List, Optional, TypeVar

import typer

from ..db.db_manager import DbManager
from ..db.postgres.postgres_manager import PostgresManager
from ..db.sqlite.sqlite_manager import SqliteManager
from ..io.cli import CliIO
from ..repository.user import create_user_id, get_user_id_if_exists
from .config import ChatModel, EmbeddingModel, get_chat_model, get_embedding_model
from .paths import get_default_config_path


class ElroyContext:
    from ..io.base import ElroyIO
    from ..io.cli import CliIO

    _db: Optional[DbManager] = None
    _io: Optional[ElroyIO] = None

    def __init__(
        self,
        *,
        # Basic Configuration
        config_path: Optional[str] = None,
        database_url: str,
        show_internal_thought: bool,
        system_message_color: str,
        assistant_color: str,
        user_input_color: str,
        warning_color: str,
        internal_thought_color: str,
        user_token: str,
        custom_tools_path: List[str] = [],
        # API Configuration
        openai_api_key: Optional[str] = None,
        openai_api_base: Optional[str] = None,
        openai_embedding_api_base: Optional[str] = None,
        openai_organization: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        # Model Configuration
        chat_model: str,
        embedding_model: str,
        embedding_model_size: int,
        enable_caching: bool = True,
        inline_tool_calls: bool = False,
        # Context Management
        max_assistant_loops: int,
        context_refresh_trigger_tokens: int,
        context_refresh_target_tokens: int,
        max_context_age_minutes: float,
        min_convo_age_for_greeting_minutes: float,
        enable_assistant_greeting: bool,
        initial_context_refresh_wait_seconds: int,
        # Memory Management
        memory_cluster_similarity_threshold: float,
        max_memory_cluster_size: int,
        min_memory_cluster_size: int,
        memories_between_consolidation: int,
        l2_memory_relevance_distance_threshold: float,
        # Basic Configuration
        debug: bool,
        default_persona: str,  # The generic persona to use if no persona is specified
        default_assistant_name: str,  # The generic assistant name to use if no assistant name is specified
    ):

        self.params = SimpleNamespace(**{k: v for k, v in locals().items() if k != "self"})

        self.user_token = user_token
        self.show_internal_thought = show_internal_thought
        self.default_assistant_name = default_assistant_name
        self.default_persona = default_persona
        self.enable_assistant_greeting = enable_assistant_greeting
        self.debug = debug
        self.context_refresh_trigger_tokens = context_refresh_trigger_tokens
        self.max_assistant_loops = max_assistant_loops
        self.context_refresh_trigger_tokens = context_refresh_trigger_tokens
        self.l2_memory_relevance_distance_threshold = l2_memory_relevance_distance_threshold
        self.context_refresh_target_tokens = context_refresh_target_tokens
        self.memory_cluster_similarity_threshold = memory_cluster_similarity_threshold
        self.min_memory_cluster_size = min_memory_cluster_size
        self.max_memory_cluster_size = max_memory_cluster_size
        self.memories_between_consolidation = memories_between_consolidation

    from ..tools.function_caller import ToolRegistry

    @cached_property
    def tool_registry(self) -> ToolRegistry:
        from ..tools.function_caller import ToolRegistry

        registry = ToolRegistry(self.params.custom_tools_path)
        registry.register_all()
        return registry

    @cached_property
    def config_path(self) -> Path:
        if self.params.config_path:
            return Path(self.params.config_path)
        else:
            return get_default_config_path()

    @property
    def initial_refresh_wait(self) -> timedelta:
        return timedelta(seconds=self.params.initial_context_refresh_wait_seconds)

    @property
    def max_in_context_message_age(self) -> timedelta:
        return timedelta(minutes=self.params.max_context_age_minutes)

    @property
    def min_convo_age_for_greeting(self) -> timedelta:
        return timedelta(minutes=self.params.min_convo_age_for_greeting_minutes)

    @cached_property
    def chat_model(self) -> ChatModel:
        return get_chat_model(
            model_name=self.params.chat_model,
            openai_api_key=self.params.openai_api_key,
            anthropic_api_key=self.params.anthropic_api_key,
            api_base=self.params.openai_api_base,
            organization=self.params.openai_organization,
            enable_caching=self.params.enable_caching,
            inline_tool_calls=self.params.inline_tool_calls,
        )

    @cached_property
    def embedding_model(self) -> EmbeddingModel:
        return get_embedding_model(
            model_name=self.params.embedding_model,
            embedding_size=self.params.embedding_model_size,
            api_key=self.params.openai_api_key,
            api_base=self.params.openai_api_base,
            organization=self.params.openai_organization,
            enable_caching=self.params.enable_caching,
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
        if not self._io:
            self._io = CliIO(
                show_internal_thought=self.params.show_internal_thought,
                system_message_color=self.params.system_message_color,
                assistant_message_color=self.params.assistant_color,
                user_input_color=self.params.user_input_color,
                warning_color=self.params.warning_color,
                internal_thought_color=self.params.internal_thought_color,
            )
        return self._io

    def set_io(self, io: ElroyIO) -> None:
        self._io = io

    @property
    def db(self) -> DbManager:
        if not self._db:
            raise ValueError("No db session open")
        else:
            return self._db

    def is_db_connected(self) -> bool:
        return bool(self._db)

    @contextmanager
    def dbsession(self) -> Generator[None, None, None]:
        """Context manager for database sessions"""
        assert self.params.database_url, "Database URL not set"

        if self.params.database_url.startswith("postgresql://"):
            db_manager = PostgresManager
        elif self.params.database_url.startswith("sqlite:///"):
            db_manager = SqliteManager
        else:
            raise ValueError(f"Unsupported database URL: {self.params.database_url}. Must be either a postgresql:// or sqlite:/// URL")

        with db_manager.open_session(self.params.database_url, True) as db:
            try:
                self._db = db
                yield
            finally:
                self._db = None


T = TypeVar("T", bound=Callable[..., Any])


def get_ctx(typer_ctx: typer.Context) -> ElroyContext:
    ctx = typer_ctx.obj
    assert isinstance(ctx, ElroyContext), f"Context must be ElroyContext, got {type(ctx)}"
    return ctx


def clone_ctx_with_db(ctx: ElroyContext, db: DbManager) -> ElroyContext:
    new_ctx = ElroyContext(**vars(ctx.params))  # type: ignore
    new_ctx._db = db
    return new_ctx
