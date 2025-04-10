QUESTION_ID = "e47becba"

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List

MESSAGES_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "messages.json")


@dataclass
class ChatMessage:
    session_datetime: datetime
    message_id: str
    role: str
    content: str

    def to_json(self):
        return {
            "session_datetime": self.session_datetime.strftime("%Y/%m/%d (%a) %H:%M"),
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
        }


def add_messages(new_messages: List[ChatMessage]):
    os.environ["ELROY_BENCHMARK_DATABASE_URL"] = "postgresql://benchmarking:password@localhost:5433/benchmarking"
    updated_msgs: List[ChatMessage] = []
    msgs: List[ChatMessage] = []

    if os.path.exists(MESSAGES_JSON_PATH):
        os.rename(MESSAGES_JSON_PATH, MESSAGES_JSON_PATH + ".bak")

    with open(MESSAGES_JSON_PATH, "r") as f:
        content = f.read()
        json_msgs = json.loads(content)
        for msg in json_msgs:
            msgs.append(
                ChatMessage(
                    session_datetime=datetime.strptime(msg["session_datetime"], "%Y/%m/%d (%a) %H:%M"),
                    message_id=msg["message_id"],
                    role=msg["role"],
                    content=msg["content"],
                )
            )

    # sort msgs by datetime
    sorted(msgs, key=lambda x: x.session_datetime)

    seen_content = set()
    for msg in msgs + new_messages:
        if msg.content not in seen_content:
            seen_content.add(msg.content)
            updated_msgs.append(msg)
    # print working dir

    with open(MESSAGES_JSON_PATH, "w") as f:
        f.write(json.dumps([m.to_json() for m in updated_msgs], indent=4))


def get_messages() -> List[ChatMessage]:
    with open(MESSAGES_JSON_PATH, "r") as f:
        content = f.read()
        json_msgs = json.loads(content)
        msgs = []
        for msg in json_msgs:
            msgs.append(
                ChatMessage(
                    session_datetime=datetime.strptime(msg["session_datetime"], "%Y/%m/%d (%a) %H:%M"),
                    message_id=msg["message_id"],
                    role=msg["role"],
                    content=msg["content"],
                )
            )

    msgs.sort(key=lambda x: x.session_datetime)

    return msgs
