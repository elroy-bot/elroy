import json
import re
from functools import partial
from typing import Dict, List, Union, Any

from toolz import pipe, curry

from ..config.config import ChatModel
from ..llm.client import query_llm


def compare_schemas(generated_schema: Dict[str, Any], expected_schema: Dict[str, Any]) -> List[str]:
    """
    Compare two JSON schemas and return a list of discrepancies.

    Args:
        generated_schema (Dict[str, Any]): The schema generated from the JSON object.
        expected_schema (Dict[str, Any]): The expected schema to compare against.

    Returns:
        List[str]: A list of discrepancies found between the schemas.
    """
    discrepancies = []

    def compare_dicts(gen: Dict[str, Any], exp: Dict[str, Any], path: str = ""):
        for key in exp:
            if key not in gen:
                discrepancies.append(f"Missing key in generated schema: {path + key}")
            else:
                if isinstance(exp[key], dict) and isinstance(gen[key], dict):
                    compare_dicts(gen[key], exp[key], path + key + ".")
                elif exp[key] != gen[key]:
                    discrepancies.append(f"Mismatch at {path + key}: expected {exp[key]}, got {gen[key]}")

    compare_dicts(generated_schema, expected_schema)
    return discrepancies


def parse_json(chat_model: ChatModel, json_str: str, attempt: int = 0) -> Union[Dict, List]:
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
