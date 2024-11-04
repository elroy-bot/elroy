import json
from dataclasses import asdict
from typing import Dict, Iterator, List, Union

from litellm import completion, embedding
from litellm.exceptions import BadRequestError
from toolz import pipe
from toolz.curried import keyfilter, map

from ..config.constants import CHAT_MODEL, EMBEDDING_MODEL
from ..repository.data_models import USER, ContextMessage
from ..utils.utils import logged_exec_time

ZERO_TEMPERATURE = 0.0


class MissingToolCallIdError(Exception):
    pass


@logged_exec_time
def generate_chat_completion_message(context_messages: List[ContextMessage]) -> Iterator[Dict]:
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
            model=CHAT_MODEL,
            tool_choice="auto",
            tools=get_function_schemas(),  # type: ignore
            stream=True,
        )  # type: ignore
    except BadRequestError as e:
        if "An assistant message with 'tool_calls' must be followed by tool messages" in str(e):
            raise MissingToolCallIdError
        else:
            raise e


def _query_llm(prompt: str, system: str, model: str, temperature: float, json_mode: bool) -> str:
    messages = [{"role": "system", "content": system}, {"role": USER, "content": prompt}]
    request = {"model": model, "messages": messages, "temperature": temperature}
    if json_mode:
        request["response_format"] = {"type": "json_object"}

    response = completion(**request)
    return response.choices[0].message.content  # type: ignore


def query_llm(prompt: str, system: str, model=CHAT_MODEL, temperature: float = ZERO_TEMPERATURE) -> str:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return _query_llm(prompt=prompt, system=system, model=model, temperature=temperature, json_mode=False)


def query_llm_json(prompt: str, system: str, model=CHAT_MODEL, temperature: float = ZERO_TEMPERATURE) -> Union[dict, list]:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return json.loads(_query_llm(prompt=prompt, system=system, model=model, temperature=temperature, json_mode=True))


def query_llm_with_word_limit(prompt: str, system: str, word_limit: int, model=CHAT_MODEL, temperature: float = ZERO_TEMPERATURE) -> str:
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
        temperature=temperature,
    )


def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> List[float]:
    """
    Generate an embedding for the given text using the specified model.

    Args:
        text (str): The input text to generate an embedding for.
        model (str): The name of the embedding model to use. Defaults to EMBEDDING_MODEL.

    Returns:
        List[float]: The generated embedding as a list of floats.
    """
    if not text:
        raise ValueError("Text cannot be empty")
    response = embedding(model=model, input=[text], caching=True)
    return response.data[0]["embedding"]
