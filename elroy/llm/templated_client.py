import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, Template
from toolz import dissoc, pipe
from toolz.curried import keyfilter, map

from ..config.config import ChatModel, EmbeddingModel
from ..config.constants import (
    ASSISTANT,
    MAX_CHAT_COMPLETION_RETRY_COUNT,
    SYSTEM,
    TOOL,
    USER,
    InvalidForceToolError,
    MaxRetriesExceededError,
    MissingToolCallMessageError,
    Provider,
)
from ..config.models import get_fallback_model
from ..repository.data_models import ContentItem, ContextMessage
from ..tools.function_caller import get_function_schemas

@dataclass
class ChatTemplate:
    """Base template for chat formatting"""
    parallel_tool_calls: bool = False
    def format_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> str:
        raise NotImplementedError

    def parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

@dataclass
class JinjaTemplate(ChatTemplate):
    """Template using Jinja2 for message formatting"""
    template_path: str = str(Path(__file__).parent.parent / "templates" / "chat.jinja")
    add_generation_prompt: bool = True

    def __post_init__(self):
        template_dir = os.path.dirname(self.template_path)
        env = Environment(loader=FileSystemLoader(template_dir), extensions=['jinja2.ext.do'])
        self.template = env.get_template(os.path.basename(self.template_path))
    def format_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """Format messages using Jinja template"""
        try:
            return self.template.render(
                messages=messages,
                tools=tools,
                parallel_tool_calls=self.parallel_tool_calls,
                add_generation_prompt=self.add_generation_prompt
            )
        except Exception as e:
            logging.error(f"Error rendering Jinja template: {e}")
            raise

    def parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Parse tool calls from generated text using ✿FUNCTION✿ markers"""
        import re
        tool_calls = []

        # Find function/args pairs
        function_matches = re.finditer(r"✿FUNCTION✿:\s*(.+?)\n✿ARGS✿:\s*(.+?)(?=\n✿(?:FUNCTION|RESULT|RETURN)✿|$)",
                                     text, re.DOTALL)

        for match in function_matches:
            try:
                name = match.group(1).strip()
                args = json.loads(match.group(2).strip())
                tool_calls.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args
                    }
                })
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse function arguments: {match.group(2)}")
                continue

        return tool_calls

class ToolCallAccumulator:
    """Accumulates and parses tool calls from streamed responses"""
    def __init__(self, chat_model: ChatModel):
        self.chat_model = chat_model
        self.current_tool_calls: List[Dict[str, Any]] = []

    def update(self, tool_calls: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Update with new tool calls and yield completed ones"""
        for tool_call in tool_calls:
            if tool_call not in self.current_tool_calls:
                self.current_tool_calls.append(tool_call)
                yield tool_call

def generate_chat_completion_message(
    chat_model: ChatModel,
    context_messages: List[ContextMessage],
    enable_tools: bool = True,
    force_tool: Optional[str] = None,
    retry_number: int = 0,
    template: Optional[ChatTemplate] = None,
) -> Iterator[Dict]:
    """
    Generates a chat completion message.
    """
    # Use default Qwen2 template if none specified
    template = template or JinjaTemplate()

    if force_tool and not enable_tools:
        logging.error("Force tool requested, but tools are disabled. Ignoring force tool request")
        force_tool = None

    if context_messages[-1].role == ASSISTANT:
        if force_tool:
            context_messages.append(
                ContextMessage(
                    role=USER,
                    content=f"User is requesting tool call: {force_tool}",
                    chat_model=chat_model.name,
                )
            )
        else:
            raise ValueError("Assistant message already the most recent message")

    # Format messages using template
    formatted_messages = template.format_messages(
        messages=[asdict(m) for m in context_messages],
        tools=get_function_schemas() if enable_tools else None
    )

    from litellm import completion
    from litellm.exceptions import BadRequestError, InternalServerError, RateLimitError

    # Make direct API call based on provider
    if chat_model.provider == Provider.OPENAI:
        import openai
        client = openai.OpenAI(api_key=chat_model.api_key, base_url=chat_model.api_base)
        response = client.chat.completions.create(
            model=chat_model.name,
            messages=[{"role": "user", "content": formatted_messages}],
            stream=True
        )
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield ContentItem(content=chunk.choices[0].delta.content)
            
            # Parse tool calls from content
            if chunk.choices[0].delta.content:
                tool_calls = template.parse_tool_calls(chunk.choices[0].delta.content)
                if tool_calls:
                    for tool_call in tool_calls:
                        yield tool_call

    elif chat_model.provider == Provider.ANTHROPIC:
        import anthropic
        client = anthropic.Anthropic(api_key=chat_model.api_key)
        response = client.messages.create(
            model=chat_model.name,
            messages=[{"role": "user", "content": formatted_messages}],
            stream=True
        )
        
        for chunk in response:
            if chunk.content:
                content = chunk.content[0].text
                yield ContentItem(content=content)
                
                # Parse tool calls from content
                tool_calls = template.parse_tool_calls(content)
                if tool_calls:
                    for tool_call in tool_calls:
                        yield tool_call

    except Exception as e:
        if isinstance(e, BadRequestError):
            if "An assistant message with 'tool_calls' must be followed by tool messages" in str(e):
                raise MissingToolCallMessageError
            else:
                raise e
        elif isinstance(e, InternalServerError) or isinstance(e, RateLimitError):
            if retry_number >= MAX_CHAT_COMPLETION_RETRY_COUNT:
                raise MaxRetriesExceededError()
            else:
                fallback_model = get_fallback_model(chat_model)
                if fallback_model:
                    logging.info(
                        f"Rate limit or internal server error for model {chat_model.name}, falling back to model {fallback_model.name}"
                    )
                    yield from generate_chat_completion_message(
                        fallback_model, context_messages, enable_tools, force_tool, retry_number + 1
                    )
                else:
                    logging.error(f"No fallback model available for {chat_model.name}, aborting")
                    raise e
        else:
            raise e

def query_llm(model: ChatModel, prompt: str, system: str) -> str:
    """Query LLM with a single prompt and system message"""
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return _query_llm(model=model, prompt=prompt, system=system)

def query_llm_with_word_limit(model: ChatModel, prompt: str, system: str, word_limit: int) -> str:
    """Query LLM with a word limit constraint"""
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return query_llm(
        prompt="\n".join(
            [
                prompt,
                f"Your word limit is {word_limit}. DO NOT EXCEED IT.",
            ]
        ),
        model=model,
        system=system,
    )

def get_embedding(model: EmbeddingModel, text: str) -> List[float]:
    """Generate an embedding for the given text"""
    from litellm import embedding

    if not text:
        raise ValueError("Text cannot be empty")
    embedding_kwargs = {
        "model": model.model,
        "input": [text],
        "caching": model.enable_caching,
        "api_key": model.api_key,
    }

    if model.api_base:
        embedding_kwargs["api_base"] = model.api_base
    if model.organization:
        embedding_kwargs["organization"] = model.organization

    response = embedding(**embedding_kwargs)
    return response.data[0]["embedding"]

def _build_completion_kwargs(
    model: ChatModel,
    messages: str,
    stream: bool,
    tool_choice: Union[str, Dict, None],
    tools: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Build kwargs for completion API call"""
    kwargs = {
        "messages": messages,
        "model": model.name,
        "api_key": model.api_key,
        "caching": model.enable_caching,
        "tool_choice": tool_choice,
        "tools": tools,
    }

    if model.api_base:
        kwargs["api_base"] = model.api_base
    if model.organization:
        kwargs["organization"] = model.organization
    if stream:
        kwargs["stream"] = True

    return kwargs

def _query_llm(model: ChatModel, prompt: str, system: str) -> str:
    """Internal function to query LLM"""
    template = JinjaTemplate(add_generation_prompt=False)
    formatted_messages = template.format_messages(
        messages=[
            {"role": SYSTEM, "content": system},
            {"role": USER, "content": prompt}
        ]
    )

    if model.provider == Provider.OPENAI:
        import openai
        client = openai.OpenAI(api_key=model.api_key, base_url=model.api_base)
        response = client.chat.completions.create(
            model=model.name,
            messages=[{"role": "user", "content": formatted_messages}],
            stream=False
        )
        return response.choices[0].message.content

    elif model.provider == Provider.ANTHROPIC:
        import anthropic
        client = anthropic.Anthropic(api_key=model.api_key)
        response = client.messages.create(
            model=model.name,
            messages=[{"role": "user", "content": formatted_messages}],
            stream=False
        )
        return response.content[0].text
