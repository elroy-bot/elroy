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
        # Model Configuration
        chat_model: Optional[str] = None,
        chat_model_api_key: Optional[str] = None,
        chat_model_api_base: Optional[str] = None,
        embedding_model: str,
        embedding_model_api_key: Optional[str] = None,
        embedding_model_api_base: Optional[str] = None,
        embedding_model_size: int,
        enable_caching: bool = True,
        inline_tool_calls: bool = False,
        # Context Management
        max_assistant_loops: int,
        max_tokens: int,
        max_context_age_minutes: float,
        min_convo_age_for_greeting_minutes: float,
        # Memory Management
        memory_cluster_similarity_threshold: float,
        max_memory_cluster_size: int,
        min_memory_cluster_size: int,
        memories_between_consolidation: int,
        messages_between_memory: int,
        l2_memory_relevance_distance_threshold: float,
        # Basic Configuration
        debug: bool,
        default_persona: Optional[str] = None,  # The generic persona to use if no persona is specified
        default_assistant_name: str,  # The generic assistant name to use if no assistant name is specified
        use_background_threads: bool,  # Whether to use background threads for certain operations
        max_ingested_doc_lines: int,  # The maximum number of lines to ingest from a document
        exclude_tools: List[str] = [],  # Tools to exclude from the tool registry
        include_base_tools: bool,
        reflect: bool,
        shell_commands: bool,
        allowed_shell_command_prefixes: List[str],
    ):
        # Create structured config objects
        self.database_config = DatabaseConfig(database_url=database_url)

        self.model_config = ModelConfig(
            openai_api_key=openai_api_key,
            openai_api_base=openai_api_base,
            openai_embedding_api_base=openai_embedding_api_base,
            chat_model=chat_model,
            chat_model_api_key=chat_model_api_key,
            chat_model_api_base=chat_model_api_base,
            embedding_model=embedding_model,
            embedding_model_api_key=embedding_model_api_key,
            embedding_model_api_base=embedding_model_api_base,
            embedding_model_size=embedding_model_size,
            enable_caching=enable_caching,
            inline_tool_calls=inline_tool_calls,
            max_tokens=max_tokens,
        )

        self.ui_config = UIConfig(
            show_internal_thought=show_internal_thought,
            system_message_color=system_message_color,
            assistant_color=assistant_color,
            user_input_color=user_input_color,
            warning_color=warning_color,
            internal_thought_color=internal_thought_color,
        )

        self.memory_config = MemoryConfig(
            max_context_age_minutes=max_context_age_minutes,
            min_convo_age_for_greeting_minutes=min_convo_age_for_greeting_minutes,
            memory_cluster_similarity_threshold=memory_cluster_similarity_threshold,
            max_memory_cluster_size=max_memory_cluster_size,
            min_memory_cluster_size=min_memory_cluster_size,
            memories_between_consolidation=memories_between_consolidation,
            messages_between_memory=messages_between_memory,
            l2_memory_relevance_distance_threshold=l2_memory_relevance_distance_threshold,
        )

        self.tool_config = ToolConfig(
            custom_tools_path=custom_tools_path,
            exclude_tools=exclude_tools,
            include_base_tools=include_base_tools,
            shell_commands=shell_commands,
            allowed_shell_command_prefixes=allowed_shell_command_prefixes,
        )

        self.runtime_config = RuntimeConfig(
            config_path=config_path,
            user_token=user_token,
            debug=debug,
            default_persona=default_persona or PERSONA,
            default_assistant_name=default_assistant_name,
            use_background_threads=use_background_threads,
            max_ingested_doc_lines=max_ingested_doc_lines,
            max_assistant_loops=max_assistant_loops,
            reflect=reflect,
        )

        # Maintain backward compatibility with direct attribute access
        self.allowed_shell_command_prefixes = [re.compile(f"^{p}") for p in allowed_shell_command_prefixes]
        self.shell_commands = shell_commands
        self.reflect = reflect
        self.include_base_tools = include_base_tools
        self.user_token = user_token
        self.show_internal_thought = show_internal_thought
        self.default_assistant_name = default_assistant_name
        self.default_persona = default_persona or PERSONA
        self.debug = debug
        self.max_tokens = max_tokens
        self.max_assistant_loops = max_assistant_loops
        self.l2_memory_relevance_distance_threshold = l2_memory_relevance_distance_threshold
        self.context_refresh_target_tokens = int(max_tokens / 3)
        self.memory_cluster_similarity_threshold = memory_cluster_similarity_threshold
        self.min_memory_cluster_size = min_memory_cluster_size
        self.max_memory_cluster_size = max_memory_cluster_size
        self.memories_between_consolidation = memories_between_consolidation
        self.messages_between_memory = messages_between_memory
        self.inline_tool_calls = inline_tool_calls
        self.use_background_threads = use_background_threads
        self.max_ingested_doc_lines = max_ingested_doc_lines

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
    def llm(self) -> LlmClient:
        return LlmClient(self.chat_model, self.embedding_model)

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
        return get_db_manager(self.database_config.database_url)

    @allow_unused
    def is_db_connected(self) -> bool:
        return bool(self._db)

    def set_db_session(self, db: DbSession):
        self._db = db

    def unset_db_session(self):
        self._db = None


T = TypeVar("T", bound=Callable[..., Any])
