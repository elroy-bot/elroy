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
from typing import Optional

from sqlalchemy import create_engine
from sqlmodel import Field, Session, SQLModel, select
from tqdm import tqdm

from elroy.api import Elroy


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
            for item in tqdm(self.input_data[:5], desc="Questions", position=0, leave=True):
                user_token = f"{self.run_token}_{item['question_id']}"
                elroy = Elroy(token=user_token, database_url=self.db_url, check_db_migration=False)
                cursor = get_or_create_cursor(session, self.run_token, item["question_id"])

                for session_idx, chat_session in enumerate(tqdm(item["haystack_sessions"], desc="Sessions", position=1, leave=False)):
                    if cursor.session_idx > session_idx:
                        continue
                    else:
                        session_date = item["haystack_dates"]
                        for message_idx, message in enumerate(tqdm(chat_session, desc="Messages", position=2, leave=False)):
                            if cursor.message_idx > message_idx:
                                continue
                            else:
                                if message["role"] == "user":
                                    elroy.message(message["content"], session_date)
                                cursor.message_idx = message_idx
                                session.add(cursor)
                                session.commit()
                                session.refresh(cursor)
                        cursor.session_idx = session_idx

                answer = Answer(
                    run_token=self.run_token,
                    question_id=item["question_id"],
                    question_type=item["question_type"],
                    question=item["question"],
                    elroy_answer=elroy.message(item["question"]),
                    answer=item["answer"],
                )
                session.add(answer)
                cursor.is_complete = True
                session.add(cursor)
                session.commit()


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
