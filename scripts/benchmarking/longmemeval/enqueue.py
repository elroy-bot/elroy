KNOWLEGE_UPDATE = [
    "01493427",
    "031748ae",
]

MULTI_SESSION = [
    "00ca467f",
    "0100672e",
]

SINGLE_SESSION_ASSISTANT = [
    "0e5e2d1a",
    "1568498a",
]

SINGLE_SESSION_PREFERENCE = [
    "06878be2",
    "06f04340",
]

SINGLE_SESSION_USER = [
    "001be529",
    "0862e8bf",
]

TEMPORAL_REASONING = [
    "08f4fc43",
    "0bb5a684",
]

QUESTION_IDS = (
    KNOWLEGE_UPDATE + MULTI_SESSION + SINGLE_SESSION_ASSISTANT + SINGLE_SESSION_PREFERENCE + SINGLE_SESSION_USER + TEMPORAL_REASONING
)

import argparse
import time
from typing import Callable

from message_processors import MESSAGE_HANDLER_FUNCS


def get_message_processor_token(run_token: str, msg_processor_func: Callable) -> str:
    return f"{run_token}__{msg_processor_func.__name__}"


def get_user_token(run_token: str, question_id: str, msg_processor_func: Callable) -> str:
    return f"{run_token}__qid__{question_id}__{msg_processor_func.__name__}"


def main():
    from run import handle

    parser = argparse.ArgumentParser(description="Process test messages using Elroy API")
    parser.add_argument("input_file", help="Path to the input JSON file containing messages")
    parser.add_argument(
        "run_token",
        nargs="?",
        default=None,
        help="Optional prefix for user tokens. If not provided, a timestamp-based prefix will be generated.",
    )

    parsed = parser.parse_args()

    run_token = parsed.run_token or f"run_{int(time.time())}"
    for question_id in QUESTION_IDS:
        for msg_handler_func in MESSAGE_HANDLER_FUNCS:
            msg_handler_func_name = msg_handler_func.__name__

            handle.delay(run_token, msg_handler_func_name, question_id)  # type: ignore
