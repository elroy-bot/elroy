from dataclasses import dataclass
from typing import Dict, List

from openai import OpenAI
from sqlmodel import Session
from toolz import pipe
from toolz.curried import do

from elroy.onboard_user import onboard_user
from elroy.system.parameters import CHAT_MODEL
from elroy.tools.messenger import process_message
from tests.utils import logging_delivery_fun

BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME = "Remember to follow through on basketball shots"


def create_test_user(session: Session, initial_messages=[]) -> int:
    """
    Returns:
        int: The ID of the created user.
    """
    user_id = onboard_user(session, "Test User")

    for message in initial_messages:
        process_message(
            session,
            user_id,
            message,
        )
    return user_id


@dataclass
class TestPersona:
    preferred_name: str
    text: str


ALEX = TestPersona(
    "Alex",
    """**Name**: Alex Johnson
**Age**: 32
**Background**: Alex has a background in law and works as a lawyer. He is a bit of a workaholic and is always looking for ways to be more efficient. He is a bit of a skeptic and is not easily impressed by new technology.
**Goals**: Alex is just trying out Elroy. He does not really know what it does. He is open to learning more, but somewhat skeptical that it will be useful. His conversation with Elroy will be exploratory and not necessarily friendly or receptive.
**Pets**: A cat named Jerry, who is known for being moody
**Hobbies** Alex loves model trains, and he has a large collection of model trains that he enjoys working on in his free time.
**Relationships** Alex's best friend is Toby, who loves model trains almost a much as Alex does.
""",
)


class SimulatedUser:
    def __init__(self, persona: TestPersona, user_id: int):
        self.client = OpenAI()
        self.name = persona.preferred_name
        self.system_instruction_message = {
            "role": "system",
            "content": f"<persona>{persona}</persona>"
            f"Your preferred name is {persona.text}."
            f"Respond as if you are this person, maintaining this persona throughout the conversation."
            f"You may receive additional prompts with events or facts about the user's life. Use these to guide your responses.",
        }
        self.messages: List[Dict[str, str]] = [self.system_instruction_message]
        self.user_id = user_id

    def send_message(self, message: str) -> str:
        self.messages.append({"role": "user", "content": message})
        response = self.client.chat.completions.create(model=CHAT_MODEL, messages=self.messages)  # type: ignore
        assistant_message = response.choices[0].message.content
        assert assistant_message
        self.messages.append({"role": "assistant", "content": assistant_message})
        return assistant_message

    def reply_to_message(self, message: str) -> str:
        temp_messages = self.messages + [{"role": "user", "content": message}]
        response = self.client.chat.completions.create(model=CHAT_MODEL, messages=temp_messages)  # type: ignore
        user_message = response.choices[0].message.content
        assert user_message
        self.messages.append({"role": "user", "content": message})
        self.messages.append({"role": "assistant", "content": user_message})
        return user_message

    def reset_messages(self) -> None:
        self.messages = [self.system_instruction_message]

    def add_system_prompt(self, prompt: str) -> None:
        self.messages.append({"role": "system", "content": prompt})

    def converse(self, session: Session, num_turns: int):
        next_message = "Hello, how are you?"
        for _i in range(num_turns):
            next_message = pipe(
                process_message(session, self.user_id, next_message),  # type: ignore
                do(logging_delivery_fun),
                lambda _: self.reply_to_message(_),
            )
