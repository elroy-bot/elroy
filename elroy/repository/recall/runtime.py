from dataclasses import dataclass

from ...core.configs import MemoryConfig
from ...core.turn import TurnContext
from ...llm.client import LlmClient


@dataclass(frozen=True)
class RecallRuntime:
    llm: LlmClient
    memory_config: MemoryConfig


def build_recall_runtime(turn: TurnContext) -> RecallRuntime:
    return RecallRuntime(
        llm=turn.config.llm,
        memory_config=turn.config.memory_config,
    )
