import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, List, Optional, TypeVar

from toolz import pipe
from toolz.curried import dissoc

from ..cli.options import DEPRECATED_KEYS, get_resolved_params, resolve_model_alias
from ..config.llm import (
    ChatModel,
    EmbeddingModel,
    get_chat_model,
    get_embedding_model,
    infer_chat_model_name,
)
from ..config.paths import get_default_config_path
from ..config.personas import PERSONA
from ..db.db_manager import DbManager, get_db_manager
from ..db.db_session import DbSession
from ..llm.client import LlmClient
from .configs import (
    DatabaseConfig,
    MemoryConfig,
    ModelConfig,
    RuntimeConfig,
    ToolConfig,
    UIConfig,
)
from .constants import allow_unused
from .logging import get_logger

logger = get_logger()


class ElroyContext:
    _db: Optional[DbSession] = None
    latency_tracker: Optional[Any] = None  # LatencyTracker, avoiding circular import

    def __init__(
        self,
        *,
        # Config objects (preferred approach)
        database_config: Optional[DatabaseConfig] = None,
        model_config: Optional[ModelConfig] = None,
        ui_config: Optional[UIConfig] = None,
        memory_config: Optional[MemoryConfig] = None,
        tool_config: Optional[ToolConfig] = None,
        runtime_config: Optional[RuntimeConfig] = None,
        # Individual parameters (for backward compatibility)
        config_path: Optional[str] = None,
        database_url: Optional[str] = None,
        vector_backend: Optional[str] = None,
        chroma_path: Optional[str] = None,
        show_internal_thought: Optional[bool] = None,
        system_message_color: Optional[str] = None,
        assistant_color: Optional[str] = None,
        user_input_color: Optional[str] = None,
        warning_color: Optional[str] = None,
        internal_thought_color: Optional[str] = None,
        user_token: Optional[str] = None,
        custom_tools_path: Optional[List[str]] = None,
        # API Configuration
        openai_api_key: Optional[str] = None,
        openai_api_base: Optional[str] = None,
        openai_embedding_api_base: Optional[str] = None,
        # Model Configuration
        chat_model: Optional[str] = None,
        chat_model_api_key: Optional[str] = None,
        chat_model_api_base: Optional[str] = None,
        fast_model: Optional[str] = None,
        fast_model_api_key: Optional[str] = None,
        fast_model_api_base: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_model_api_key: Optional[str] = None,
        embedding_model_api_base: Optional[str] = None,
        embedding_model_size: Optional[int] = None,
        enable_caching: Optional[bool] = None,
        inline_tool_calls: Optional[bool] = None,
        # Context Management
        max_assistant_loops: Optional[int] = None,
        max_tokens: Optional[int] = None,
        max_context_age_minutes: Optional[float] = None,
        min_convo_age_for_greeting_minutes: Optional[float] = None,
        # Memory Management
        memory_cluster_similarity_threshold: Optional[float] = None,
        max_memory_cluster_size: Optional[int] = None,
        min_memory_cluster_size: Optional[int] = None,
        memories_between_consolidation: Optional[int] = None,
        messages_between_memory: Optional[int] = None,
        l2_memory_relevance_distance_threshold: Optional[float] = None,
        memory_recall_classifier_enabled: Optional[bool] = None,
        memory_recall_classifier_window: Optional[int] = None,
        # Basic Configuration
        debug: Optional[bool] = None,
        default_persona: Optional[str] = None,
        default_assistant_name: Optional[str] = None,
        use_background_threads: Optional[bool] = None,
        max_ingested_doc_lines: Optional[int] = None,
        exclude_tools: Optional[List[str]] = None,
        include_base_tools: Optional[bool] = None,
        reflect: Optional[bool] = None,
        shell_commands: Optional[bool] = None,
        allowed_shell_command_prefixes: Optional[List[str]] = None,
        # Background Ingestion
        background_ingest_enabled: Optional[bool] = None,
        background_ingest_paths: Optional[List[str]] = None,
        background_ingest_interval_minutes: Optional[int] = None,
    ):
        # Handle both config objects approach and individual parameters approach
        if database_config is not None:
            self.database_config = database_config
        else:
            self.database_config = DatabaseConfig(
                database_url=database_url or "",
                vector_backend=vector_backend or "auto",
                chroma_path=chroma_path,
            )

        if model_config is not None:
            self.model_config = model_config
        else:
            self.model_config = ModelConfig(
                openai_api_key=openai_api_key,
                openai_api_base=openai_api_base,
                openai_embedding_api_base=openai_embedding_api_base,
                chat_model=chat_model,
                chat_model_api_key=chat_model_api_key,
                chat_model_api_base=chat_model_api_base,
                fast_model=fast_model,
                fast_model_api_key=fast_model_api_key,
                fast_model_api_base=fast_model_api_base,
                embedding_model=embedding_model or "text-embedding-3-small",
                embedding_model_api_key=embedding_model_api_key,
                embedding_model_api_base=embedding_model_api_base,
                embedding_model_size=embedding_model_size or 1536,
                enable_caching=enable_caching if enable_caching is not None else True,
                inline_tool_calls=inline_tool_calls if inline_tool_calls is not None else False,
                max_tokens=max_tokens or 4000,
            )

        if ui_config is not None:
            self.ui_config = ui_config
        else:
            self.ui_config = UIConfig(
                show_internal_thought=show_internal_thought if show_internal_thought is not None else False,
                system_message_color=system_message_color or "bright_blue",
                assistant_color=assistant_color or "bright_green",
                user_input_color=user_input_color or "bright_yellow",
                warning_color=warning_color or "bright_red",
                internal_thought_color=internal_thought_color or "dim",
            )

        if memory_config is not None:
            self.memory_config = memory_config
        else:
            self.memory_config = MemoryConfig(
                max_context_age_minutes=max_context_age_minutes or 60.0,
                min_convo_age_for_greeting_minutes=min_convo_age_for_greeting_minutes or 5.0,
                memory_cluster_similarity_threshold=memory_cluster_similarity_threshold or 0.85,
                max_memory_cluster_size=max_memory_cluster_size or 10,
                min_memory_cluster_size=min_memory_cluster_size or 2,
                memories_between_consolidation=memories_between_consolidation or 5,
                messages_between_memory=messages_between_memory or 10,
                l2_memory_relevance_distance_threshold=l2_memory_relevance_distance_threshold or 0.7,
                memory_recall_classifier_enabled=memory_recall_classifier_enabled if memory_recall_classifier_enabled is not None else True,
                memory_recall_classifier_window=memory_recall_classifier_window or 3,
            )

        if tool_config is not None:
            self.tool_config = tool_config
        else:
            self.tool_config = ToolConfig(
                custom_tools_path=custom_tools_path or [],
                exclude_tools=exclude_tools or [],
                include_base_tools=include_base_tools if include_base_tools is not None else True,
                shell_commands=shell_commands if shell_commands is not None else True,
                allowed_shell_command_prefixes=allowed_shell_command_prefixes or [],
            )

        if runtime_config is not None:
            self.runtime_config = runtime_config
        else:
            self.runtime_config = RuntimeConfig(
                config_path=config_path,
                user_token=user_token or "",
                debug=debug if debug is not None else False,
                default_persona=default_persona or PERSONA,
                default_assistant_name=default_assistant_name or "",
                use_background_threads=use_background_threads if use_background_threads is not None else True,
                max_ingested_doc_lines=max_ingested_doc_lines or 0,
                max_assistant_loops=max_assistant_loops or 0,
                reflect=reflect if reflect is not None else False,
                background_ingest_enabled=background_ingest_enabled if background_ingest_enabled is not None else False,
                background_ingest_paths=background_ingest_paths or [],
                background_ingest_interval_minutes=background_ingest_interval_minutes or 60,
            )

        # Maintain backward compatibility with direct attribute access
        self.allowed_shell_command_prefixes = [re.compile(f"^{p}") for p in self.tool_config.allowed_shell_command_prefixes]
        self.shell_commands = self.tool_config.shell_commands
        self.reflect = self.runtime_config.reflect
        self._include_base_tools = self.tool_config.include_base_tools
        self.user_token = self.runtime_config.user_token
        self.show_internal_thought = self.ui_config.show_internal_thought
        self.default_assistant_name = self.runtime_config.default_assistant_name
        self.default_persona = self.runtime_config.default_persona
        self.debug = self.runtime_config.debug
        self.max_tokens = self.model_config.max_tokens
        self.max_assistant_loops = self.runtime_config.max_assistant_loops
        self.l2_memory_relevance_distance_threshold = self.memory_config.l2_memory_relevance_distance_threshold
        self.context_refresh_target_tokens = int(self.model_config.max_tokens / 3)
        self.memory_cluster_similarity_threshold = self.memory_config.memory_cluster_similarity_threshold
        self.min_memory_cluster_size = self.memory_config.min_memory_cluster_size
        self.max_memory_cluster_size = self.memory_config.max_memory_cluster_size
        self.memories_between_consolidation = self.memory_config.memories_between_consolidation
        self.messages_between_memory = self.memory_config.messages_between_memory
        self.inline_tool_calls = self.model_config.inline_tool_calls
        self.use_background_threads = self.runtime_config.use_background_threads
        self.max_ingested_doc_lines = self.runtime_config.max_ingested_doc_lines
        self.background_ingest_enabled = self.runtime_config.background_ingest_enabled
        self.background_ingest_paths = self.runtime_config.background_ingest_paths
        self.background_ingest_interval_minutes = self.runtime_config.background_ingest_interval_minutes

    @property
    def include_base_tools(self) -> bool:
        return self._include_base_tools

    @include_base_tools.setter
    def include_base_tools(self, value: bool):
        self._include_base_tools = value
        self.tool_config.include_base_tools = value
        # Clear cached tool_registry so it gets recreated with new include_base_tools value
        if "tool_registry" in self.__dict__:
            del self.__dict__["tool_registry"]

    from ..tools.registry import ToolRegistry

    @classmethod
    def init(cls, **kwargs):
        from ..cli.main import CLI_ONLY_PARAMS, MODEL_ALIASES

        for m in MODEL_ALIASES:
            if kwargs.get(m):
                logger.info(f"Model alias {m} selected")
                resolved = resolve_model_alias(m)
                if not resolved:
                    logger.warning("Model alias not found")
                else:
                    kwargs["chat_model"] = resolved

            if m in kwargs:
                del kwargs[m]

        params = pipe(
            kwargs,
            lambda x: get_resolved_params(**x),
            lambda x: dissoc(x, *CLI_ONLY_PARAMS),
        )

        invalid_params = set(params.keys()) - set(ElroyContext.__init__.__annotations__.keys())

        for k in invalid_params:
            if k in DEPRECATED_KEYS:
                logger.warning(f"Ignoring deprecated config (will be removed in future releases): '{k}'")
            else:
                logger.warning(f"Ignoring invalid parameter: {k}")

        return cls(**dissoc(params, *invalid_params))  # type: ignore

    @cached_property
    def tool_registry(self) -> ToolRegistry:
        from ..tools.registry import ToolRegistry

        registry = ToolRegistry(
            self.tool_config.include_base_tools,
            self.tool_config.custom_tools_path,
            exclude_tools=self.tool_config.exclude_tools,
            shell_commands=self.tool_config.shell_commands,
            allowed_shell_command_prefixes=self.allowed_shell_command_prefixes,
        )
        registry.register_all()
        return registry

    @cached_property
    def config_path(self) -> Path:
        if self.runtime_config.config_path:
            return Path(self.runtime_config.config_path)
        else:
            return get_default_config_path()

    @cached_property
    def thread_pool(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor()

    @property
    def max_in_context_message_age(self) -> timedelta:
        return timedelta(minutes=self.memory_config.max_context_age_minutes)

    @property
    def min_convo_age_for_greeting(self) -> timedelta:
        return timedelta(minutes=self.memory_config.min_convo_age_for_greeting_minutes)

    @property
    def is_chat_model_inferred(self) -> bool:
        return self.model_config.chat_model is None

    @cached_property
    def chat_model(self) -> ChatModel:
        if not self.model_config.chat_model:
            chat_model_name = infer_chat_model_name()
        else:
            chat_model_name = self.model_config.chat_model

        return get_chat_model(
            model_name=chat_model_name,
            openai_api_key=self.model_config.openai_api_key,
            openai_api_base=self.model_config.openai_api_base,
            api_key=self.model_config.chat_model_api_key,
            api_base=self.model_config.chat_model_api_base,
            enable_caching=self.model_config.enable_caching,
            inline_tool_calls=self.model_config.inline_tool_calls,
        )

    @cached_property
    def fast_model(self) -> ChatModel:
        """Fast model for background tasks (summarization, classification, etc.)"""
        # If no fast_model configured, fall back to chat_model
        if not self.model_config.fast_model:
            return self.chat_model

        return get_chat_model(
            model_name=self.model_config.fast_model,
            openai_api_key=self.model_config.openai_api_key,
            openai_api_base=self.model_config.openai_api_base,
            api_key=self.model_config.fast_model_api_key,
            api_base=self.model_config.fast_model_api_base,
            enable_caching=self.model_config.enable_caching,
            inline_tool_calls=False,  # Fast model doesn't need inline tool calls
        )

    @cached_property
    def llm(self) -> LlmClient:
        return LlmClient(self.chat_model, self.embedding_model)

    @cached_property
    def fast_llm(self) -> LlmClient:
        """Fast LLM client for background tasks (summarization, classification, etc.)"""
        return LlmClient(self.fast_model, self.embedding_model)

    @cached_property
    def embedding_model(self) -> EmbeddingModel:
        return get_embedding_model(
            model_name=self.model_config.embedding_model,
            embedding_size=self.model_config.embedding_model_size,
            api_key=self.model_config.embedding_model_api_key,
            api_base=self.model_config.embedding_model_api_base,
            openai_embedding_api_base=self.model_config.openai_embedding_api_base,
            openai_api_key=self.model_config.openai_api_key,
            openai_api_base=self.model_config.openai_api_base,
            enable_caching=self.model_config.enable_caching,
        )

    @cached_property
    def user_id(self) -> int:
        from ..repository.user.operations import create_user_id
        from ..repository.user.queries import get_user_id_if_exists

        return get_user_id_if_exists(self.db, self.runtime_config.user_token) or create_user_id(self.db, self.runtime_config.user_token)

    @property
    def db(self) -> DbSession:
        if not self._db:
            raise ValueError("No db session open")
        else:
            return self._db

    @cached_property
    def db_manager(self) -> DbManager:
        assert self.database_config.database_url, "Database URL not set"
        return get_db_manager(
            self.database_config.database_url,
            self.database_config.vector_backend,
            chroma_path=self.database_config.chroma_path,
        )

    @allow_unused
    def is_db_connected(self) -> bool:
        return bool(self._db)

    def set_db_session(self, db: DbSession):
        self._db = db

    def unset_db_session(self):
        self._db = None


T = TypeVar("T", bound=Callable[..., Any])
