from collections.abc import Callable
from dataclasses import dataclass

from toolz import pipe

from ...core.constants import (
    FORMATTING_INSTRUCT,
    SYSTEM,
    SYSTEM_INSTRUCTION_LABEL,
    SYSTEM_INSTRUCTION_LABEL_END,
)
from ...tools.inline_tools import inline_tool_instruct
from ...tools.registry import ToolRegistry
from .data_models import ContextMessage
from .transforms import remove


@dataclass(frozen=True)
class SystemPromptMetadataProviders:
    get_persona_fn: Callable[[], str]


class SystemPromptBuilder:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        chat_model_inline_tool_calls: bool,
        metadata_providers: SystemPromptMetadataProviders,
    ):
        self.tool_registry = tool_registry
        self.chat_model_inline_tool_calls = chat_model_inline_tool_calls
        self.metadata_providers = metadata_providers

    def build(self) -> ContextMessage:
        return pipe(
            [
                SYSTEM_INSTRUCTION_LABEL,
                f"<persona>{self.metadata_providers.get_persona_fn()}</persona>",
                FORMATTING_INSTRUCT,
                inline_tool_instruct(self.tool_registry.get_schemas()) if self.chat_model_inline_tool_calls else None,
                "From now on, converse as your persona.",
                SYSTEM_INSTRUCTION_LABEL_END,
            ],
            remove(lambda _: _ is None),
            list,
            "\n".join,
            lambda x: ContextMessage(role=SYSTEM, content=x, chat_model=None),
        )
