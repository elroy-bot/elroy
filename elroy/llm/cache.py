import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Type, Union

from pydantic import BaseModel

from ..config.llm import ChatModel, EmbeddingModel


def _is_test_environment() -> bool:
    """Check if we're running in a test environment."""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.environ.get("_", "") or any("pytest" in arg for arg in os.sys.argv)


def _get_cache_dir() -> Path:
    """Get the cache directory for test data."""
    cache_dir = Path(__file__).parent.parent.parent / "tests" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _create_cache_key(data: Dict[str, Any]) -> str:
    """Create a deterministic cache key from request data."""
    # Sort keys to ensure consistent hashing
    normalized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _serialize_for_json(obj):
    """Convert objects to JSON-serializable format."""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif hasattr(obj, "__dict__"):
        # Recursively serialize object attributes
        return {k: _serialize_for_json(v) for k, v in obj.__dict__.items()}
    elif hasattr(obj, "_asdict"):  # namedtuple
        return {k: _serialize_for_json(v) for k, v in obj._asdict().items()}
    else:
        # Fallback: convert to string
        return str(obj)


def _save_to_cache(cache_key: str, data: Any, cache_type: str) -> None:
    """Save data to cache file."""
    if not _is_test_environment():
        return

    cache_dir = _get_cache_dir()
    cache_file = cache_dir / f"{cache_type}_{cache_key}.json"

    # Serialize the data to handle non-JSON objects
    serialized_data = _serialize_for_json(data)

    with open(cache_file, "w") as f:
        json.dump(serialized_data, f, indent=2)


def _load_from_cache(cache_key: str, cache_type: str) -> Optional[Any]:
    """Load data from cache file."""
    if not _is_test_environment():
        return None

    cache_dir = _get_cache_dir()
    cache_file = cache_dir / f"{cache_type}_{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


class CachedStreamResponse:
    """Simulate streaming response from cached data."""

    def __init__(self, cached_data: Dict[str, Any], model_name: str):
        self.cached_content = cached_data.get("content", "")
        self.cached_tool_calls = cached_data.get("tool_calls", [])
        self.model_name = model_name
        self._index = 0
        self._tool_calls_sent = False

    def __iter__(self):
        return self

    def __next__(self):
        from litellm.types.utils import Delta, ModelResponse, StreamingChoices

        # First send tool calls if any exist
        if not self._tool_calls_sent and self.cached_tool_calls:
            self._tool_calls_sent = True
            # Reconstruct tool calls from cached data
            from litellm.types.utils import ChatCompletionDeltaToolCall, Function

            reconstructed_tool_calls = []
            for tc in self.cached_tool_calls:
                if isinstance(tc, dict):
                    # Reconstruct from serialized data
                    function = Function(arguments=tc.get("function", {}).get("arguments", ""), name=tc.get("function", {}).get("name", ""))
                    tool_call = ChatCompletionDeltaToolCall(
                        id=tc.get("id", ""), function=function, type=tc.get("type", "function"), index=tc.get("index", 0)
                    )
                    reconstructed_tool_calls.append(tool_call)
                else:
                    # Already a proper object
                    reconstructed_tool_calls.append(tc)

            return ModelResponse(
                choices=[StreamingChoices(delta=Delta(tool_calls=reconstructed_tool_calls), finish_reason=None)], model=self.model_name
            )

        # Then stream content character by character
        if self._index >= len(self.cached_content):
            raise StopIteration

        # Simulate streaming character by character
        char = self.cached_content[self._index]
        self._index += 1

        # Simulate slight delay for realism
        time.sleep(0.001)

        return ModelResponse(
            choices=[
                StreamingChoices(delta=Delta(content=char), finish_reason="stop" if self._index >= len(self.cached_content) else None)
            ],
            model=self.model_name,
        )


def cache_embedding_call(model: EmbeddingModel, text: str, original_func) -> List[float]:
    """Cache wrapper for embedding calls."""
    if not _is_test_environment():
        return original_func(model, text)

    # Create cache key from model and text
    cache_data = {"model_name": model.name, "text": text, "call_type": "embedding"}
    cache_key = _create_cache_key(cache_data)

    # Try to load from cache
    cached_result = _load_from_cache(cache_key, "embedding")
    if cached_result is not None:
        return cached_result["embedding"]

    # Call original function and cache result
    result = original_func(model, text)
    _save_to_cache(cache_key, {"embedding": result}, "embedding")

    return result


def cache_query_llm_call(model: ChatModel, prompt: str, system: str, response_format: Optional[Type[BaseModel]], original_func) -> str:
    """Cache wrapper for query_llm calls."""
    if not _is_test_environment():
        return original_func(model, prompt, system, response_format)

    # Create cache key from parameters
    cache_data = {
        "model_name": model.name,
        "prompt": prompt,
        "system": system,
        "response_format": str(response_format) if response_format else None,
        "call_type": "query_llm",
    }
    cache_key = _create_cache_key(cache_data)

    # Try to load from cache
    cached_result = _load_from_cache(cache_key, "query_llm")
    if cached_result is not None:
        return cached_result["response"]

    # Call original function and cache result
    result = original_func(model, prompt, system, response_format)
    _save_to_cache(cache_key, {"response": result}, "query_llm")

    return result


def cache_completion_call(
    chat_model: ChatModel,
    context_messages: List[Dict[str, Any]],
    tool_schemas: List[Dict[str, Any]],
    enable_tools: bool,
    force_tool: Optional[str],
    original_func,
) -> Union[Iterator, Any]:
    """Cache wrapper for completion calls."""
    if not _is_test_environment():
        return original_func(chat_model, context_messages, tool_schemas, enable_tools, force_tool)

    # Create cache key from parameters
    cache_data = {
        "model_name": chat_model.name,
        "context_messages": context_messages,
        "tool_schemas": tool_schemas,
        "enable_tools": enable_tools,
        "force_tool": force_tool,
        "call_type": "completion",
    }
    cache_key = _create_cache_key(cache_data)

    # Try to load from cache
    cached_result = _load_from_cache(cache_key, "completion")
    if cached_result is not None:
        # Return cached streaming response
        return CachedStreamResponse(cached_result, chat_model.name)

    # Call original function and collect all streamed content
    stream = original_func(chat_model, context_messages, tool_schemas, enable_tools, force_tool)

    # Collect all content and tool calls from the stream
    collected_content = ""
    collected_tool_calls = []
    collected_responses = []

    for response in stream:
        collected_responses.append(response)
        if hasattr(response, "choices") and response.choices:
            delta = response.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                collected_content += delta.content
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                collected_tool_calls.extend(delta.tool_calls)

    # Cache the collected content and tool calls
    cache_payload = {"content": collected_content, "tool_calls": collected_tool_calls}
    _save_to_cache(cache_key, cache_payload, "completion")

    # Return the original responses (for this first run)
    return iter(collected_responses)
