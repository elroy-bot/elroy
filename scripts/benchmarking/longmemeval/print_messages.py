QUESTION_ID = "e47becba"

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import partial

from sqlmodel import Session
from toolz import concat, pipe
from toolz.curried import map

from db import (
    ChatSession,
    get_engine,
    get_messages_for_session,
    get_sessions_for_question,
)


@dataclass
class ChatMessage2:
    session_datetime: datetime
    message_id: str
    role: str
    content: str


def main():
    os.environ["ELROY_BENCHMARK_DATABASE_URL"] = "postgresql://benchmarking:password@localhost:5433/benchmarking"
    output = []
    with Session(get_engine()) as session:
        chat_sessions = get_sessions_for_question(session, "af082822")
        chat_sessions += get_sessions_for_question(session, "f9e8c073")
        chat_sessions += get_sessions_for_question(session, "5a4f22c0")

        chat_sessions = pipe(
            ["af082822", "f9e8c073", "5a4f22c0"],
            map(partial(get_sessions_for_question, session)),
            concat,
            list,
        )

        msgs = []
        for chat_session in chat_sessions:
            assert isinstance(chat_session, ChatSession)
            for message in get_messages_for_session(session, chat_session.session_id):
                msgs.append(
                    ChatMessage2(
                        session_datetime=datetime.strptime(chat_session.session_date, "%Y/%m/%d (%a) %H:%M"),
                        message_id=str(uuid.uuid4()),
                        role=message.role,
                        content=message.content,
                    )
                )

        with open("messages.json", "r") as f:
            content = f.read()
            json_msgs = json.loads(content)
            for msg in json_msgs:
                msgs.append(
                    ChatMessage2(
                        session_datetime=datetime.strptime(msg["session_datetime"], "%Y/%m/%d (%a) %H:%M"),
                        message_id=msg["message_id"],
                        role=msg["role"],
                        content=msg["content"],
                    )
                )

        # sort msgs by datetime
        sorted(msgs, key=lambda x: x.session_datetime)

        seen_content = set()
        for msg in msgs:
            if msg.content not in seen_content:
                seen_content.add(msg.content)
                output.append(
                    {
                        # convert msg.session_datetime to string
                        "session_datetime": msg.session_datetime.strftime("%Y/%m/%d (%a) %H:%M"),
                        "message_id": msg.message_id,
                        "role": msg.role,
                        "content": msg.content,
                    }
                )
    with open("messages_2.json", "w") as f:
        f.write(json.dumps(output, indent=4))


if __name__ == "__main__":
    main()
