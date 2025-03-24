#!/usr/bin/env python3

"""
Script to process test messages from an input JSON file using Elroy API.
The script simulates chat logs by recording messages and creating memories periodically.
"""

import argparse
import json
import sys
import time
from functools import cached_property
from pathlib import Path
from typing import List, Optional

from sqlalchemy import create_engine
from sqlmodel import Session, select
from tqdm import tqdm

from elroy.api import Elroy
from elroy.core.constants import SYSTEM
from elroy.core.tracing import tracer
from scripts.benchmarking.longmemeval.setup_benchmarking_db import Answer, Cursor, get_or_create_cursor, update_or_create_answer


class BenchmarkingRun:
    db_file: Path = Path("./elroy.db")

    def __init__(self, input_file: str, run_token: Optional[str] = None):
        self.input_file = input_file
        self.run_token = run_token or f"run_{int(time.time())}"

    @cached_property
    def input_data(self):
        try:
            with open(self.input_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {self.input_file} is not a valid JSON file")
            sys.exit(1)
        except FileNotFoundError:
            print(f"Error: File {self.input_file} not found")
            sys.exit(1)

    @property
    def db_url(self):
        return f"sqlite:///elroy.db"

    def run(self):
        # Initialize database
        from scripts.benchmarking.longmemeval.setup_benchmarking_db import init_db
        engine = init_db(self.db_url)

        # Initialize cursor entries using SQLAlchemy session
        with Session(engine) as session:
            for item in tqdm(self.input_data[:100], desc="Questions", position=0, leave=True):
                user_token = f"{self.run_token}_{item['question_id']}"
                elroy = Elroy(
                    token=user_token,
                    database_url=self.db_url,
                    check_db_migration=False,
                )
                cursor = get_or_create_cursor(session, self.run_token, item["question_id"])

                @tracer.agent
                def handle_msg(msg: str, question_id: str, haystack_session_id: int, message_idx: int):
                    return elroy.message(msg)

                for session_idx, chat_session in enumerate(tqdm(item["haystack_sessions"], desc="Sessions", position=1, leave=False)):
                    if cursor.session_idx > session_idx:
                        # logging.warning(f"skipping session {session_idx} because it is behind cursor {cursor.session_idx}")
                        continue
                    else:
                        session_date = item["haystack_dates"]
                        elroy.record_message(SYSTEM, f"The user has initiated a chat session. The current time is: {session_date}")
                        for message_idx, message in enumerate(tqdm(chat_session, desc="Messages", position=2, leave=False)):
                            if cursor.message_idx > message_idx:
                                # logging.warning(f"skipping message {message_idx} because it is behind cursor {cursor.message_idx}")
                                continue
                            else:

                                if message["role"] == "user":
                                    handle_msg(
                                        message["content"],
                                        item["question_id"],
                                        item["haystack_session_ids"][session_idx],
                                        message_idx,
                                    )
                                    elroy.message(message["content"])

                                cursor.message_idx = message_idx
                                session.add(cursor)
                                session.commit()
                                session.refresh(cursor)
                        elroy.context_refresh()
                        cursor.session_idx = session_idx
                        cursor.message_idx = -1
                        session.commit()
                        session.refresh(cursor)
                cursor.session_idx += 1
                cursor.message_idx = -1
                session.commit()
                session.refresh(cursor)

                elroy.ctx.show_internal_thought = False

                update_or_create_answer(
                    session,
                    self.run_token,
                    item["question_id"],
                    item["question_type"],
                    question=item["question"],
                    elroy_answer=elroy.message(
                        "the following is a test of your memory. Respond simply and concisely. Just give your answer, do not continue the conversation. E.g. if the question is: What is 2+2? Respond simply with: 4. Use tools to search for information, if you don't know say I don't know.: "
                        + item["question"]
                    ),
                    answer=item["answer"],
                    answer_session_ids=item["answer_session_ids"],
                )

                elroy.ctx.show_internal_thought = True
                cursor.is_complete = True
                session.add(cursor)
                session.commit()
                session.refresh(cursor)


def main():
    parser = argparse.ArgumentParser(description="Process test messages using Elroy API")
    parser.add_argument("input_file", help="Path to the input JSON file containing messages", default="data/longmemeval_s.json")
    parser.add_argument(
        "run_token",
        nargs="?",
        default=None,
        help="Optional prefix for user tokens. If not provided, a timestamp-based prefix will be generated.",
    )

    args = parser.parse_args()
    BenchmarkingRun(args.input_file, args.run_token).run()


if __name__ == "__main__":
    main()
