QUESTION_ID = "e47becba"

import argparse
import json
import os
import uuid

from sqlmodel import Session

from db import get_engine, get_messages_for_session, get_sessions_for_question


def main():

    parser = argparse.ArgumentParser(description="Process test messages using Elroy API")
    parser.add_argument("question_id", help="Path to the input JSON file containing messages", default=QUESTION_ID)
    parsed = parser.parse_args()

    os.environ["ELROY_BENCHMARK_DATABASE_URL"] = "postgresql://benchmarking:password@localhost:5433/benchmarking"
    output = []
    with Session(get_engine()) as session:
        for chat_session in get_sessions_for_question(session, parsed.question_id):
            chat_session.session_date
            for message in get_messages_for_session(session, QUESTION_ID, chat_session.session_id):
                output.append(
                    {
                        "session_datetime": chat_session.session_date,
                        "message_id": str(uuid.uuid4()),
                        "role": message.role,
                        "content": message.content,
                    }
                )
    with open("messages.json", "w") as f:
        f.write(json.dumps(output, indent=4))


if __name__ == "__main__":
    main()
