from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    """Database connection and session configuration."""

    database_url: str
    vector_backend: str = "auto"  # "auto", "sqlite" (native), or "chroma"
    chroma_path: str | None = None


@dataclass
class ModelConfig:
    """LLM and embedding model configuration."""

    # API Configuration
    openai_api_key: str | None = None
    openai_api_base: str | None = None
    openai_embedding_api_base: str | None = None

    # Chat Model Configuration (Strong Model - used for main conversation)
    chat_model: str | None = None
    chat_model_api_key: str | None = None
    chat_model_api_base: str | None = None

    # Fast Model Configuration (used for background tasks: summarization, classification, etc.)
    fast_model: str | None = None
    fast_model_api_key: str | None = None
    fast_model_api_base: str | None = None

    # Embedding Model Configuration
    embedding_model: str = "text-embedding-3-small"
    embedding_model_api_key: str | None = None
    embedding_model_api_base: str | None = None
    embedding_model_size: int = 1536

    # Model Behavior
    enable_caching: bool = True
    inline_tool_calls: bool = False
    max_tokens: int = 4000


@dataclass
class UIConfig:
    """User interface and display configuration."""

    show_internal_thought: bool = False
    system_message_color: str = "bright_blue"
    assistant_color: str = "bright_green"
    user_input_color: str = "bright_yellow"
    warning_color: str = "bright_red"
    internal_thought_color: str = "dim"


@dataclass
class MemoryConfig:
    """Memory management and context configuration."""

    # Context Management
    max_context_age_minutes: float = 60.0
    min_convo_age_for_greeting_minutes: float = 5.0

    # Memory Clustering
    memory_cluster_similarity_threshold: float = 0.85
    max_memory_cluster_size: int = 10
    min_memory_cluster_size: int = 2
    memories_between_consolidation: int = 5
    messages_between_memory: int = 10
    l2_memory_relevance_distance_threshold: float = 0.7

    # Memory Recall Classifier
    memory_recall_classifier_enabled: bool = True
    memory_recall_classifier_window: int = 3


@dataclass
class ToolConfig:
    """Tool and command configuration."""

    custom_tools_path: list[str]
    exclude_tools: list[str]
    allowed_shell_command_prefixes: list[str]
    include_base_tools: bool = True
    shell_commands: bool = True


@dataclass
class RuntimeConfig:
    """Runtime behavior and performance configuration."""

    user_token: str
    default_assistant_name: str
    max_assistant_loops: int
    max_ingested_doc_lines: int
    config_path: str | None = None
    debug: bool = False
    default_persona: str | None = None
    use_background_threads: bool = True
    reflect: bool = False
    background_ingest_paths: list[str] = field(default_factory=list)
    background_ingest_interval_minutes: int = 60
    background_ingest_enabled: bool = False
