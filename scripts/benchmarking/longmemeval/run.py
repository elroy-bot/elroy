#!/usr/bin/env python3

"""
Script to process test messages from an input JSON file using Elroy API.
The script simulates chat logs by recording messages and creating memories periodically.
"""

import argparse
import os
import sys
import time
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the current directory to the path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from setup_benchmarking_db import (
    Cursor,
    get_messages_for_session,
    get_or_create_cursor,
    get_question_by_id,
    get_sessions_for_question,
    load_benchmark_data,
    update_or_create_answer,
)
from sqlmodel import Session, select
from tqdm import tqdm

from elroy.api import Elroy
from elroy.core.constants import SYSTEM
from elroy.core.tracing import tracer


class BenchmarkingRun:
    db_file: Path = Path("./elroy.db")

    def __init__(self, input_file: str, run_token: Optional[str] = None):
        self.input_file = input_file
        self.run_token = run_token or f"run_{int(time.time())}"

    @cached_property
    def input_data(self) -> List[Dict[str, Any]]:
        try:
            return load_benchmark_data(self.input_file)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)

    @property
    def db_url(self):
        return f"sqlite:///elroy.db"

    def run(self):
        # Initialize database
        from setup_benchmarking_db import (
            check_run_exists,
            import_benchmark_data,
            init_db,
        )

        engine = init_db(self.db_url)

        # Import data if needed
        with Session(engine) as session:
            # Check if questions table is empty
            from sqlalchemy import func

            question_count = session.exec(select(func.count()).select_from(Question)).one()
            if question_count == 0:
                print("Database is empty. Importing benchmark data...")
                import_benchmark_data(session, self.input_data)

        # Check if this run already exists in the database
        with Session(engine) as session:
            run_exists = session.exec(select(Cursor).where(Cursor.run_token == self.run_token)).count() > 0
            if run_exists:
                print(f"Run with token '{self.run_token}' already exists in the database.")
                print("Resuming from last saved position...")
            else:
                print(f"Starting new run with token '{self.run_token}'")

        # Initialize cursor entries using SQLAlchemy session
        with Session(engine) as session:
            # Limit to first 100 questions for testing
            question_limit = 100

            # Get all questions from the database
            questions = list(session.exec(select(Question).limit(question_limit)))

            for question in tqdm(questions, desc="Questions", position=0, leave=True):
                question_id = question.question_id
                user_token = f"{self.run_token}_{question_id}"
                elroy = Elroy(
                    token=user_token,
                    database_url=self.db_url,
                    check_db_migration=False,
                )
                # Get question details
                question = get_question_by_id(session, question_id)
                if not question:
                    print(f"Question {question_id} not found in database. Skipping.")
                    continue

                cursor = get_or_create_cursor(session, self.run_token, question_id)

                @tracer.agent
                def handle_msg(msg: str, question_id: str, session_id: str, message_idx: int):
                    return elroy.message(msg)

                # Get all sessions for this question
                chat_sessions = get_sessions_for_question(session, question_id)

                for session_idx, chat_session in enumerate(tqdm(chat_sessions, desc="Sessions", position=1, leave=False)):
                    if cursor.session_idx > session_idx:
                        # Skip sessions we've already processed
                        continue
                    else:
                        session_date = chat_session.session_date
                        elroy.record_message(SYSTEM, f"The user has initiated a chat session. The current time is: {session_date}")
                        # Get all messages for this session
                        messages = get_messages_for_session(session, chat_session.session_id)

                        for message_idx, message in enumerate(tqdm(messages, desc="Messages", position=2, leave=False)):
                            if cursor.message_idx > message_idx:
                                # Skip messages we've already processed
                                continue
                            else:
                                if message.role == "user":
                                    handle_msg(
                                        message.content,
                                        question_id,
                                        chat_session.session_id,
                                        message_idx,
                                    )
                                    elroy.message(message.content)

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
                    question.question_id,
                    question.question_type,
                    question=question.question,
                    elroy_answer=elroy.message(
                        "the following is a test of your memory. Respond simply and concisely. Just give your answer, do not continue the conversation. E.g. if the question is: What is 2+2? Respond simply with: 4. Use tools to search for information, if you don't know say I don't know.: "
                        + question.question
                    ),
                    answer=question.answer,
                    answer_session_ids=[s.session_id for s in chat_sessions if s.is_answer_session],
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
