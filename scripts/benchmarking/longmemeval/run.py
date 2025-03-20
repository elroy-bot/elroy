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

from sqlmodel import SQLModel
from tqdm import tqdm

from elroy.api import Elroy


class Cursor(SQLModel):
    user_token: str
    session_idx: str
    message_idx: int


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

    def init_run(self):
        Elroy(token=self.run_token, database_url=self.db_url).init_db()


        # create table if not exists: cursor. AI!
        # columns: run_token (str), question_id (str), session_idx (int, default = -1), message_idx (int, default = -1), is_complete (bool, default = false)
        # unique on: run _token, session_idx

        # create table if not exists: questions: question_id (str), question (str), answer (str), expected_answer (str)

        for i in self.input_data:
            ...
            # check if a cursor entry exists, if not create: run_token = self.run_token, question_id = i["question_id"], session_idx = -1, message_idx = -1, is_complete = False

        return


def process_messages(input_file, token_prefix=None):
    """
    Process messages from the input JSON file.

    Args:
        input_file (str): Path to the input JSON file
        token_prefix (str, optional): Prefix for user tokens. If None, a timestamp-based prefix will be generated.
    """
    # Generate token prefix based on timestamp if not provided
    if token_prefix is None:
        token_prefix = f"user_{int(time.time())}"

    # Create a directory for SQLite databases if it doesn't exist
    db_dir = Path("./cache")
    db_dir.mkdir(exist_ok=True)

    try:
        with open(input_file, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {input_file} is not a valid JSON file")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: File {input_file} not found")
        sys.exit(1)

    # Process each question with its own user token and database
    for q in data:
        process_question_message(q, token_prefix, db_dir)
        return


def process_question_message(data, token_prefix, db_dir):
    """
    Process messages for a specific question.

    Args:
        token_prefix (str): Prefix for user token
        db_dir (Path): Directory for SQLite databases
    """
    question_id = data["question_id"]
    question = data["question"]
    answer = data["answer"]

    db_url = f"sqlite:///{db_dir}.db"
    ai = Elroy(token=token_prefix + question_id, database_url=db_url, check_db_migration=True)

    for session_idx, session in enumerate(tqdm(data["haystack_sessions"], desc="Sessions", position=0, leave=True)):
        for msgs_idx, message in tqdm(session, desc="Messages", position=1, leave=False):
            import pdb

            pdb.set_trace()
            ai.record_message(message["role"], message["content"])

    ai_answer = ai.message(question)

    output = {"question_id": question_id, "question": question, "answer": answer, "ai_answer": ai_answer}
    print(output)


def main():
    parser = argparse.ArgumentParser(description="Process test messages using Elroy API")
    parser.add_argument("input_file", help="Path to the input JSON file containing messages")
    parser.add_argument(
        "token_prefix",
        nargs="?",
        default=None,
        help="Optional prefix for user tokens. If not provided, a timestamp-based prefix will be generated.",
    )

    args = parser.parse_args()

    process_messages(args.input_file, args.token_prefix)


if __name__ == "__main__":
    main()
