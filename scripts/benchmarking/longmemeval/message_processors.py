import os
import sys
from typing import Callable

from phoenix.trace import suppress_tracing

# Add the current directory to the path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import sys

from db import ChatMessage
from elroy.api import Elroy
from elroy.core.constants import USER


def ai_assistant_response_to_chat(
    ai: Elroy,
    chat_message: ChatMessage,
):
    if chat_message.role == USER and chat_message.has_answer:
        return ai.message(chat_message.content)
    else:
        with suppress_tracing():
            return ai.message(chat_message.content)


def harcoded_assistant_response_to_chat(ai: Elroy, chat_message: ChatMessage) -> str:
    with suppress_tracing():
        return ai.record_message(chat_message.role, chat_message.content) or "recorded"


MESSAGE_HANDLER_FUNCS = [
    harcoded_assistant_response_to_chat,
    ai_assistant_response_to_chat,
]


def get_message_handler_func(
    message_processor_name: str,
) -> Callable:
    for func in MESSAGE_HANDLER_FUNCS:
        if func.__name__ == message_processor_name:
            return func
    raise ValueError(f"Unknown message processor name: {message_processor_name}")
