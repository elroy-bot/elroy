from dataclasses import dataclass

from ..core.turn import TurnContext
from ..llm.client import LlmClient


@dataclass(frozen=True)
class MemoRuntime:
    llm: LlmClient
    fast_llm: LlmClient


def build_memo_runtime(turn: TurnContext) -> MemoRuntime:
    return MemoRuntime(
        llm=turn.config.llm,
        fast_llm=turn.config.fast_llm,
    )
