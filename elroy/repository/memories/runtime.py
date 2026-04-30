from dataclasses import dataclass
from pathlib import Path

from ...core.configs import MemoryConfig
from ...core.turn import TurnContext
from ...llm.client import LlmClient


@dataclass(frozen=True)
class MemoryRuntime:
    memory_dir_path: Path
    fast_llm: LlmClient
    memory_config: MemoryConfig
    llm: LlmClient
    reflect: bool
    memories_between_consolidation: int


def build_memory_runtime(turn: TurnContext) -> MemoryRuntime:
    config = turn.config
    return MemoryRuntime(
        memory_dir_path=config.memory_dir_path,
        fast_llm=config.fast_llm,
        memory_config=config.memory_config,
        llm=config.llm,
        reflect=config.reflect,
        memories_between_consolidation=config.memories_between_consolidation,
    )
