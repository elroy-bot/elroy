from typing import Callable, List

from messages import ChatMessage
from phoenix.trace import suppress_tracing

from elroy.api import Elroy

# Add the current directory to the path to ensure imports work


def ai_assistant_response_to_chat(
    ai: Elroy,
    chat_message: ChatMessage,
):
    with suppress_tracing():
        return ai.message(chat_message.content)


def harcoded_assistant_response_to_chat(ai: Elroy, chat_message: ChatMessage) -> str:
    with suppress_tracing():
        return ai.record_message(chat_message.role, chat_message.content) or "recorded"


def harcoded_assistant_response_to_chat_10(ai: Elroy, chat_message: ChatMessage) -> str:
    with suppress_tracing():
        ai.ctx.messages_between_memory = 10
        return ai.record_message(chat_message.role, chat_message.content) or "recorded"


def harcoded_assistant_response_to_chat_05(ai: Elroy, chat_message: ChatMessage) -> str:
    with suppress_tracing():
        ai.ctx.messages_between_memory = 5
        return ai.record_message(chat_message.role, chat_message.content) or "recorded"


MESSAGE_FUNCS: List[Callable[[Elroy, ChatMessage], str]] = [
    ai_assistant_response_to_chat,
    harcoded_assistant_response_to_chat,
    harcoded_assistant_response_to_chat_05,
    harcoded_assistant_response_to_chat_10,
]


def get_message_func(name: str):
    for func in MESSAGE_FUNCS:
        if func.__name__ == name:
            return func
    raise ValueError(f"Unknown answer function: {name}")
