import json
import logging
import re
from functools import partial
from typing import Dict, List, Tuple, Union

from toolz import pipe

from ..config.config import ChatModel
from .client import _query_llm


def parse_json(chat_model: ChatModel, json_str: str, attempt: int = 0) -> Union[Dict, List]:
    from .client import query_llm

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


def extract_title_and_body(response: str) -> Tuple[str, str]:
    """Extract title and body from markdown formatted response.

    Supports various markdown title formats:
    - # Title
    - #Title
    - ## Title
    - ###Title
    etc.

    Args:
        response: Markdown formatted string with title and body

    Returns:
        Tuple of (title, body)

    Raises:
        ValueError: If no valid title format is found
    """
    lines = response.strip().split("\n")
    if not lines:
        raise ValueError("Empty response")

    # Find first non-empty line
    title_line = next((line for line in lines if line.strip()), "")

    # Match any number of #s followed by optional space and title text

    title_match = re.match(r"^#+\s*(.+)$", title_line)

    if not title_match:
        logging.info("No title Markdown formatting found for title, accepting first line as title.")
        title = title_line.strip()

    else:
        title = title_match.group(1).strip()
    body = "\n".join(line for line in lines[1:] if line.strip()).strip()

    return (title, body)
