from typing import Any, Dict, Iterator, List, Optional

from ..config.llm import ChatModel


class MockStreamParser:
    """
    A mock StreamParser that replays cached streaming responses.
    
    This class mimics the behavior of the real StreamParser but instead
    of making actual API calls, it replays cached responses from previous
    test runs.
    """
    
    def __init__(self, chat_model: ChatModel, cached_data: Dict[str, Any]):
        self.chat_model = chat_model
        self.cached_data = cached_data
        
        # Extract cached content
        self.message_content = cached_data.get("message_content", "")
        self.tool_calls = cached_data.get("tool_calls", [])
        self._chunks = cached_data.get("chunks", [])
        self._chunk_index = 0
        self._is_done = False
    
    def __iter__(self) -> Iterator:
        return self
    
    def __next__(self) -> Any:
        if self._chunk_index >= len(self._chunks) or self._is_done:
            self._is_done = True
            raise StopIteration
        
        chunk = self._chunks[self._chunk_index]
        self._chunk_index += 1
        return chunk
    
    @property
    def is_done(self) -> bool:
        """Check if the stream is done."""
        return self._is_done or self._chunk_index >= len(self._chunks)
    
    def get_message_content(self) -> str:
        """Get the accumulated message content."""
        return self.message_content
    
    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """Get the accumulated tool calls."""
        return self.tool_calls