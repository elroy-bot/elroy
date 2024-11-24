import json
import re
from functools import partial
from typing import Dict, List, Union

from toolz import pipe

from ..config.config import ChatModel
from .client import _query_llm


def parse_json(chat_model: ChatModel, json_str: str, attempt: int = 0) -> Union[Dict, List]:
    from ..llm.client import query_llm

    cleaned_str = pipe(
        json_str,
        str.strip,
        partial(re.sub, r"^```json", ""),
        str.strip,
        partial(re.sub, r"```$", ""),
        str.strip,
    )

    try:
        return json.loads(cleaned_str.strip())
    except json.JSONDecodeError as e:
        if attempt > 3:
            raise e
        else:
            return pipe(
                query_llm(
                    chat_model,
                    system=f"You will be given a text that is malformed JSON. An attempt to parse it has failed with error: {str(e)}."
                    "Repair the json and return it. Respond with nothing but the repaired JSON."
                    "If at all possible maintain the original structure of the JSON, in your repairs bias towards the smallest edit you can make to form valid JSON",
                    prompt=cleaned_str,
                ),
                lambda x: parse_json(chat_model, x, attempt + 1),
            )  # type: ignore


def query_llm_json(model: ChatModel, prompt: str, system: str) -> Union[dict, list]:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return pipe(
        _query_llm(model=model, prompt=prompt, system=system),
        partial(parse_json, model),
    )  # type: ignore
