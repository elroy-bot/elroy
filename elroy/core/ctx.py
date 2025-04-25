from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, List, Optional, TypeVar

from toolz import pipe
from toolz.curried import dissoc

from ..cli.options import DEPRECATED_KEYS, get_resolved_params, resolve_model_alias
from ..config.paths import get_default_config_path
from ..config.personas import PERSONA
from .config import ElroyConfig
from .logging import get_logger
from .services.database import DatabaseService
from .services.llm import LLMService
from .services.memory import MemoryService
from .services.tools import ToolService
from .services.user import UserService

logger = get_logger()


class ElroyContext:
    """Facade that provides access to all services and configuration"""

    _db = None  # Kept for backward compatibility

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
        **kwargs,  # Allow additional parameters for backward compatibility
    ):
        # Store all configuration in a single object
        all_params = locals()
        all_params.pop("self")
        all_params.pop("kwargs")
        all_params.update(kwargs)

        self.config = ElroyConfig(**all_params)
        self.params = self.config  # For backward compatibility

        # Copy frequently accessed config parameters to the top level for backward compatibility
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
        self.reflect = reflect
        self.include_base_tools = include_base_tools
        self.shell_commands = shell_commands

        # For backward compatibility with code that accesses these directly
        import re

        self.allowed_shell_command_prefixes = [re.compile(f"^{p}") for p in allowed_shell_command_prefixes]

        # Initialize service references (but not the services themselves)
        self._db_service = None
        self._llm_service = None
        self._tool_service = None
        self._user_service = None
        self._memory_service = None
        self._thread_pool = None

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
                del kwargs[m]

        params = pipe(
            kwargs,
            lambda x: dissoc(x, *CLI_ONLY_PARAMS),
            lambda x: get_resolved_params(**x),
        )

        invalid_params = set(params.keys()) - set(cls.__init__.__annotations__.keys()) - {"kwargs"}

        for k in invalid_params:
            if k in DEPRECATED_KEYS:
                logger.warning(f"Ignoring deprecated config (will be removed in future releases): '{k}'")
            else:
                logger.warning(f"Ignoring invalid parameter: {k}")

        return cls(**{k: v for k, v in params.items() if k not in invalid_params})

    # Service accessors with lazy initialization

    @cached_property
    def db_service(self):
        if not self._db_service:
            self._db_service = DatabaseService(self.config)
        return self._db_service

    @cached_property
    def llm_service(self):
        if not self._llm_service:
            self._llm_service = LLMService(self.config)
        return self._llm_service

    @cached_property
    def tool_service(self):
        if not self._tool_service:
            self._tool_service = ToolService(self.config)
        return self._tool_service

    @cached_property
    def user_service(self):
        if not self._user_service:
            self._user_service = UserService(self.config, self.db_service)
        return self._user_service

    @cached_property
    def memory_service(self):
        if not self._memory_service:
            self._memory_service = MemoryService(self.config)
        return self._memory_service

    # Delegate properties to maintain backward compatibility

    @property
    def db(self):
        return self.db_service.db

    @property
    def db_manager(self):
        return self.db_service.db_manager

    @property
    def is_chat_model_inferred(self):
        return self.llm_service.is_chat_model_inferred

    @property
    def chat_model(self):
        return self.llm_service.chat_model

    @property
    def embedding_model(self):
        return self.llm_service.embedding_model

    @property
    def tool_registry(self):
        return self.tool_service.tool_registry

    @property
    def user_id(self):
        return self.user_service.user_id

    @property
    def max_in_context_message_age(self):
        return self.memory_service.max_in_context_message_age

    @property
    def min_convo_age_for_greeting(self):
        return self.memory_service.min_convo_age_for_greeting

    @cached_property
    def thread_pool(self) -> ThreadPoolExecutor:
        if not self._thread_pool:
            self._thread_pool = ThreadPoolExecutor()
        return self._thread_pool

    @cached_property
    def config_path(self) -> Path:
        if self.config.config_path:
            return Path(self.config.config_path)
        else:
            return get_default_config_path()

    # Database session management (for backward compatibility)

    def is_db_connected(self) -> bool:
        return self.db_service.is_db_connected()

    def set_db_session(self, db):
        self._db = db  # For backward compatibility
        self.db_service.set_db_session(db)

    def unset_db_session(self):
        self._db = None  # For backward compatibility
        self.db_service.unset_db_session()


T = TypeVar("T", bound=Callable[..., Any])
