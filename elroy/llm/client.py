import json
from dataclasses import asdict
from typing import Dict, Iterator, List, Union

from litellm import completion, embedding
from litellm.exceptions import BadRequestError
from toolz import pipe
from toolz.curried import keyfilter, map

from ..config.config import ChatModel, EmbeddingModel
from ..repository.data_models import USER, ContextMessage
from ..utils.utils import logged_exec_time


class MissingToolCallIdError(Exception):
    pass


@logged_exec_time
def generate_chat_completion_message(chat_model: ChatModel, context_messages: List[ContextMessage]) -> Iterator[Dict]:
    from ..tools.function_caller import get_function_schemas

    context_messages = pipe(
        context_messages,
        map(asdict),
        map(keyfilter(lambda k: k not in ("id", "created_at"))),
        list,
    )

    try:
        return completion(
            messages=context_messages,
            model=chat_model.model,
            api_key=chat_model.api_key,
            tool_choice="auto",
            tools=get_function_schemas(),  # type: ignore
            stream=True,
        )  # type: ignore
    except BadRequestError as e:
        if "An assistant message with 'tool_calls' must be followed by tool messages" in str(e):
            raise MissingToolCallIdError
        else:
            raise e


def _query_llm(model: ChatModel, prompt: str, system: str, json_mode: bool) -> str:
    messages = [{"role": "system", "content": system}, {"role": USER, "content": prompt}]
    request = {"model": model.model, "messages": messages}
    if model.api_key:
        request["api_key"] = model.api_key

    if json_mode:
        request["response_format"] = {"type": "json_object"}

    response = completion(**request)
    return response.choices[0].message.content  # type: ignore


def query_llm(model: ChatModel, prompt: str, system: str) -> str:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return _query_llm(model=model, prompt=prompt, system=system, json_mode=False)


def query_llm_json(model: ChatModel, prompt: str, system: str) -> Union[dict, list]:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return json.loads(_query_llm(model=model, prompt=prompt, system=system, json_mode=True))


def query_llm_with_word_limit(model: ChatModel, prompt: str, system: str, word_limit: int) -> str:
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
    """
    Generate an embedding for the given text using the specified model.

    Args:
        text (str): The input text to generate an embedding for.
        model (str): The name of the embedding model to use.

    Returns:
        List[float]: The generated embedding as a list of floats.
    """
    if not text:
        raise ValueError("Text cannot be empty")
    response = embedding(model=model.model, input=[text], caching=True)
    return response.data[0]["embedding"]
