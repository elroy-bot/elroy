import platform
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from rich.text import Text

from .. import __version__
from ..config.paths import get_home_dir
from ..llm.client import LlmClient
from ..tools.registry import ToolRegistry
from .ctx import ElroyConfig
from .turn import TurnContext


@dataclass(frozen=True)
class ConversationRuntime:
    llm: LlmClient
    tool_schemas: list[dict]
    inline_tool_calls: bool
    max_assistant_loops: int
    show_internal_thought: bool
    chat_model_name: str
    memory_recall_classifier_enabled: bool


@dataclass(frozen=True)
class ToolExecutionRuntime:
    tool_registry: ToolRegistry


@dataclass(frozen=True)
class RecallClassifierRuntime:
    fast_llm: LlmClient
    window_size: int


@dataclass(frozen=True)
class CommandRuntime:
    tool_registry: ToolRegistry
    thread_pool: ThreadPoolExecutor


@dataclass(frozen=True)
class ConfigReportRuntime:
    config_path: str
    debug: bool
    default_assistant_name: str
    user_token: str
    database_url: str
    chat_model_name: str
    embedding_model_name: str
    embedding_model_size: int
    caching_enabled: bool
    chat_api_base: str
    chat_api_key: str | None
    embeddings_api_base: str
    embeddings_api_key: str | None
    max_assistant_loops: int
    max_tokens: int
    context_refresh_target_tokens: int
    max_context_age_minutes: float
    memory_dir: str
    memory_cluster_similarity: float
    max_memory_cluster_size: int
    min_memory_cluster_size: int
    memories_between_consolidation: int
    l2_memory_relevance_distance: float
    show_internal_thought: bool
    system_message_color: Text
    assistant_color: Text
    user_input_color: Text
    warning_color: Text
    internal_thought_color: Text


@dataclass(frozen=True)
class UiRuntime:
    chat_model_name: str
    min_convo_age_for_greeting: timedelta


@dataclass(frozen=True)
class BackgroundTaskRuntime:
    use_background_threads: bool


@dataclass(frozen=True)
class InlineToolRuntime:
    inline_tool_calls: bool


@dataclass(frozen=True)
class MemoryFileSyncRuntime:
    memory_dir_path: Path


def build_conversation_runtime(turn: TurnContext) -> ConversationRuntime:
    config = turn.config
    return ConversationRuntime(
        llm=config.llm,
        tool_schemas=config.tool_registry.get_schemas(),
        inline_tool_calls=config.chat_model.inline_tool_calls,
        max_assistant_loops=config.max_assistant_loops,
        show_internal_thought=config.show_internal_thought,
        chat_model_name=config.chat_model.name,
        memory_recall_classifier_enabled=config.memory_config.memory_recall_classifier_enabled,
    )


def build_tool_execution_runtime(turn: TurnContext) -> ToolExecutionRuntime:
    return ToolExecutionRuntime(tool_registry=turn.config.tool_registry)


def build_recall_classifier_runtime(turn: TurnContext) -> RecallClassifierRuntime:
    config = turn.config
    return RecallClassifierRuntime(
        fast_llm=config.fast_llm,
        window_size=config.memory_config.memory_recall_classifier_window,
    )


def build_ui_runtime(config: ElroyConfig) -> UiRuntime:
    return UiRuntime(
        chat_model_name=config.chat_model.name,
        min_convo_age_for_greeting=config.min_convo_age_for_greeting,
    )


def build_background_task_runtime(config: ElroyConfig) -> BackgroundTaskRuntime:
    return BackgroundTaskRuntime(use_background_threads=config.use_background_threads)


def build_inline_tool_runtime(config: ElroyConfig) -> InlineToolRuntime:
    return InlineToolRuntime(inline_tool_calls=config.inline_tool_calls)


def build_memory_file_sync_runtime(turn: TurnContext) -> MemoryFileSyncRuntime:
    return MemoryFileSyncRuntime(memory_dir_path=turn.config.memory_dir_path)


def build_command_runtime(config: ElroyConfig) -> CommandRuntime:
    return CommandRuntime(
        tool_registry=config.tool_registry,
        thread_pool=config.thread_pool,
    )


def build_config_report_runtime(config: ElroyConfig) -> ConfigReportRuntime:
    return ConfigReportRuntime(
        config_path=str(config.config_path),
        debug=config.debug,
        default_assistant_name=config.default_assistant_name,
        user_token=config.user_token,
        database_url=config.database_url,
        chat_model_name=config.chat_model.name,
        embedding_model_name=config.embedding_model.name,
        embedding_model_size=config.model_config.embedding_model_size,
        caching_enabled=config.model_config.enable_caching,
        chat_api_base=config.chat_model.api_base or "None (May be read from env vars)",
        chat_api_key=config.chat_model.api_key,
        embeddings_api_base=config.embedding_model.api_base or "None (May be read from env vars)",
        embeddings_api_key=config.embedding_model.api_key,
        max_assistant_loops=config.max_assistant_loops,
        max_tokens=config.max_tokens,
        context_refresh_target_tokens=config.context_refresh_target_tokens,
        max_context_age_minutes=config.memory_config.max_context_age_minutes,
        memory_dir=str(config.memory_dir_path) if config.memory_dir_path else "None",
        memory_cluster_similarity=config.memory_cluster_similarity_threshold,
        max_memory_cluster_size=config.max_memory_cluster_size,
        min_memory_cluster_size=config.min_memory_cluster_size,
        memories_between_consolidation=config.memories_between_consolidation,
        l2_memory_relevance_distance=config.l2_memory_relevance_distance_threshold,
        show_internal_thought=config.show_internal_thought,
        system_message_color=Text(config.ui_config.system_message_color, style=config.ui_config.system_message_color),
        assistant_color=Text(config.ui_config.assistant_color, style=config.ui_config.assistant_color),
        user_input_color=Text(config.ui_config.user_input_color, style=config.ui_config.user_input_color),
        warning_color=Text(config.ui_config.warning_color, style=config.ui_config.warning_color),
        internal_thought_color=Text(config.ui_config.internal_thought_color, style=config.ui_config.internal_thought_color),
    )


def build_system_info_runtime() -> dict[str, str]:
    return {
        "OS": f"{platform.system()} {platform.release()}",
        "Python Version": platform.python_version(),
        "Python Location": sys.executable,
        "Elroy Version": __version__,
        "Elroy Home Dir": str(get_home_dir()),
    }
