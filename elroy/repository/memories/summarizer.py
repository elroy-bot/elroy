from collections.abc import Callable
from dataclasses import dataclass

from ...core.constants import MAX_MEMORY_LENGTH
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage


@dataclass(frozen=True)
class MemorySummarizerMetadataProviders:
    get_user_preferred_name_fn: Callable[[], str | None]
    get_assistant_name_fn: Callable[[], str]


class MemorySummarizer:
    def __init__(self, fast_llm: LlmClient, metadata_providers: MemorySummarizerMetadataProviders):
        self.fast_llm = fast_llm
        self.metadata_providers = metadata_providers

    def formulate_memory(self, context_messages: list[ContextMessage]) -> tuple[str, str]:
        from ...llm.prompts import summarize_for_memory
        from ..context_messages.transforms import format_context_messages

        user_preferred_name = self.metadata_providers.get_user_preferred_name_fn() or "User"

        return summarize_for_memory(
            self.fast_llm,
            format_context_messages(
                context_messages,
                user_preferred_name,
                self.metadata_providers.get_assistant_name_fn(),
            ),
            user_preferred_name,
        )

    def ensure_memory_title(self, text: str, name: str | None = None) -> str:
        if not text:
            raise ValueError("Memory text cannot be empty.")

        if len(text) > MAX_MEMORY_LENGTH:
            raise ValueError(f"Memory text exceeds maximum length of {MAX_MEMORY_LENGTH} characters.")

        if name:
            return name

        return self.fast_llm.query_llm(
            system="Given text representing a memory, your task is to come up with a short title for a memory. "
            "If the title mentions dates, it should be specific dates rather than relative ones.",
            prompt=text,
        )
