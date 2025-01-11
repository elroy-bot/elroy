from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, Iterator, List, Optional, TypeVar

from ..db.db_models import FunctionCall
from ..repository.data_models import StreamItem

T = TypeVar("T", str, StreamItem)

# TODO: Convert existing parsing into this class
# the template should also influence the system message


@dataclass
class ParsedContent:
    """Container for parsed content from LLM output"""

    main_content: str = ""
    internal_thought: Optional[str] = None
    function_calls: List[FunctionCall] = field(default_factory=list)


class StreamParser(ABC, Generic[T]):
    """Abstract base class for parsing streaming LLM output content"""

    @abstractmethod
    def process(self, chunks: Iterator[T]) -> Iterator[StreamItem]:
        """Process a chunk of content and yield parsed items

        Args:
            chunk: A piece of content from the LLM (either StreamItem or str)

        Returns:
            Iterator of ContentItem (for main content and thoughts)
            or FunctionCall objects
        """
        raise NotImplementedError
