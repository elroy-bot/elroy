#!/usr/bin/env python3

"""
Script to process test messages from an input JSON file using Elroy API.
The script simulates chat logs by recording messages and creating memories periodically.
"""

import argparse
import json
import logging
import sys
import time
from functools import cached_property
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlmodel import Field, Session, SQLModel, select
from tqdm import tqdm

from elroy.api import Elroy
from elroy.core.constants import SYSTEM


class Cursor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_token: str
    question_id: str
    session_idx: int = -1
    message_idx: int = -1
    is_complete: bool = False


class Answer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_token: str
    question_id: str
    question_type: str
    question: str
    elroy_answer: str
    answer: str


def get_or_create_cursor(session: Session, run_token: str, question_id: str):
    cursor = session.exec(select(Cursor).where(Cursor.run_token == run_token).where(Cursor.question_id == question_id)).first()

    if not cursor:
        # Create new cursor entry
        cursor = Cursor(run_token=run_token, question_id=question_id)
        session.add(cursor)

        session.commit()
    return cursor


def update_or_create_answer(
    session: Session,
    run_token: str,
    question_id: str,
    question_type: str,
    question: str,
    elroy_answer: str,
    answer: str,
):
    answer_row = session.exec(select(Answer).where(Answer.run_token == run_token).where(Answer.question_id == question_id)).first()

    if answer_row:
        answer_row.elroy_answer = elroy_answer
    else:
        answer_row = Answer(
            run_token=run_token,
            question_id=question_id,
            question_type=question_type,
            question=question,
            elroy_answer=elroy_answer,
            answer=answer,
        )
    session.add(answer_row)
    session.commit()


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
        # Create engine and cursor table using SQLAlchemy directly
        engine = create_engine(self.db_url)
        SQLModel.metadata.create_all(engine)

        # Initialize cursor entries using SQLAlchemy session
        with Session(engine) as session:
            for item in tqdm(self.input_data, desc="Questions", position=0, leave=True):
                user_token = f"{self.run_token}_{item['question_id']}"
                elroy = Elroy(
                    token=user_token,
                    database_url=self.db_url,
                    check_db_migration=False,
                )
                cursor = get_or_create_cursor(session, self.run_token, item["question_id"])

                for session_idx, chat_session in enumerate(tqdm(item["haystack_sessions"], desc="Sessions", position=1, leave=False)):
                    if cursor.session_idx > session_idx:
                        logging.warning(f"skipping session {session_idx} because it is behind cursor {cursor.session_idx}")
                        continue
                    else:
                        session_date = item["haystack_dates"]
                        elroy.record_message(SYSTEM, f"The user has initiated a chat session. The current time is: {session_date}")
                        for message_idx, message in enumerate(tqdm(chat_session, desc="Messages", position=2, leave=False)):
                            if cursor.message_idx > message_idx:
                                logging.warning(f"skipping message {message_idx} because it is behind cursor {cursor.message_idx}")
                                continue
                            else:
                                if message["role"] == "user":
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
