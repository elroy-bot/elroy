from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DatabaseConfig:
    """Database connection and session configuration."""

    database_url: str


@dataclass
class ModelConfig:
    """LLM and embedding model configuration."""

    # API Configuration
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    openai_embedding_api_base: Optional[str] = None

    # Chat Model Configuration
    chat_model: Optional[str] = None
    chat_model_api_key: Optional[str] = None
    chat_model_api_base: Optional[str] = None

    # Embedding Model Configuration
    embedding_model: str = "text-embedding-3-small"
    embedding_model_api_key: Optional[str] = None
    embedding_model_api_base: Optional[str] = None
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


@dataclass
class ToolConfig:
    """Tool and command configuration."""

    custom_tools_path: List[str]
    exclude_tools: List[str]
    allowed_shell_command_prefixes: List[str]
    include_base_tools: bool = True
    shell_commands: bool = True


@dataclass
class RuntimeConfig:
    """Runtime behavior and performance configuration."""

    user_token: str
    default_assistant_name: str
    max_assistant_loops: int
    max_ingested_doc_lines: int
    config_path: Optional[str] = None
    debug: bool = False
    default_persona: Optional[str] = None
    use_background_threads: bool = True
    reflect: bool = False
