import re
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, TypeVar

from openai.types.completion import Completion

from ..db.db_models import FunctionCall
from ..repository.data_models import AssistantResponseChunk, StreamItem
from .parser import StreamParser

T = TypeVar("T", str, StreamItem)

# TODO: Convert existing parsing into this class
# the template should also influence the system message

FUNCTION_START_SEQ = "✿"
# FUNCTION_START_SEQ = "✿FUNCTION✿"
FUNCTION_END_EXP = r"^✿RESULT✿.*\n"


@dataclass
class ParsedContent:
    """Container for parsed content from LLM output"""

    main_content: str = ""
    internal_thought: Optional[str] = None
    function_calls: List[FunctionCall] = field(default_factory=list)


class TemplateParser(StreamParser):
    """Abstract base class for parsing streaming LLM output content"""

    def __init__(self):
        self.function_str = None
        super().__init__()

    def process(self, chunks: Iterator[Completion]) -> Iterator[StreamItem]:
        """Process a chunk of content and yield parsed items

        Args:
            chunk: A piece of content from the LLM (either StreamItem or str)

        Returns:
            Iterator of ContentItem (for main content and thoughts)
            or FunctionCall objects
        """
        for completion_chunk in chunks:
            choice = completion_chunk.choices[0]
            if choice.finish_reason == "stop":
                return
            else:
                chunk = choice.text
            if self.function_str:
                if chunk is None:
                    import pdb

                    pdb.set_trace()
                self.function_str += chunk
                if re.search(FUNCTION_END_EXP, self.function_str):
                    yield self.get_function_call(self.function_str)
                    self.function_str = None
            elif FUNCTION_START_SEQ in chunk:
                self.function_str = chunk
            else:
                yield AssistantResponseChunk(content=chunk)

    def get_function_call(self, function_str: str) -> FunctionCall:
        import pdb

        pdb.set_trace()
        raise ValueError
