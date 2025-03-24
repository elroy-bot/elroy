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
from typing import Optional

# Add the current directory to the path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from benchmarking_db import (
    get_messages_for_session,
    get_or_create_cursor,
    get_question_by_id,
    get_questions,
    get_sessions_for_question,
    update_or_create_answer,
)
from sqlmodel import Session, create_engine
from tqdm import tqdm

from elroy.api import Elroy
from elroy.core.constants import SYSTEM
from elroy.core.tracing import tracer


class QuestionEvaluator:

    def __init__(self, session: Session, db_url: str, question_id: str, run_token: Optional[str] = None):
        self.session = session
        self.db_url = db_url
        self.question_id = question_id
        self.run_token = run_token or f"run_{int(time.time())}"
        self.user_token = f"{self.run_token}_{self.question_id}"

    @cached_property
    def ai(self) -> Elroy:
        return Elroy(
            token=self.user_token,
            database_url=self.db_url,
            check_db_migration=False,
        )

    @tracer.agent
    def handle_msg(self, msg: str, question_id: str, session_id: str, message_idx: int):
        return self.ai.message(msg)

    @tracer.agent
    def record_answer(self):
        question = get_question_by_id(self.session, self.question_id)

        assert question

        try:
            self.ai.ctx.show_internal_thought = False

            update_or_create_answer(
                self.session,
                self.run_token,
                question.question_id,
                question.question_type,
                question=question.question,
                elroy_answer=self.ai.message(
                    f"""The following is a test of your memory.
                    Just give your answer, do not continue the conversation.
                    E.g. if the question is: What is 2+2? Respond simply with: 4.
                    Use tools to search for information!
                    If you don't know even after using tools, say if you don't know say I don't know.:
                    {question.question}"""
                ),
                answer=question.answer,
                answer_session_ids=question.answer_session_ids,
            )
        finally:
            self.ai.ctx.show_internal_thought = True

    def run(self):
        cursor = get_or_create_cursor(self.session, self.run_token, self.question_id)
        chat_sessions = get_sessions_for_question(self.session, self.question_id)

        for session_idx, chat_session in enumerate(tqdm(chat_sessions, desc="Sessions", position=1, leave=False)):
            if cursor.session_idx > session_idx:
                # Skip sessions we've already processed
                continue
            else:
                session_date = chat_session.session_date
                self.ai.record_message(SYSTEM, f"The user has initiated a chat session. The current time is: {session_date}")
                # Get all messages for this session
                messages = get_messages_for_session(self.session, chat_session.session_id)

                for message_idx, message in enumerate(tqdm(messages, desc="Messages", position=2, leave=False)):
                    if cursor.message_idx > message_idx:
                        # Skip messages we've already processed
                        continue
                    else:
                        if message.role == "user":
                            self.handle_msg(
                                message.content,
                                self.question_id,
                                chat_session.session_id,
                                message_idx,
                            )

                        cursor.message_idx = message_idx
                        self.session.add(cursor)
                        self.session.commit()
                        self.session.refresh(cursor)
                self.ai.context_refresh()
                cursor.session_idx = session_idx
                cursor.message_idx = -1
                self.session.commit()
                self.session.refresh(cursor)
            cursor.session_idx += 1
            cursor.message_idx = -1
            self.session.commit()
            self.session.refresh(cursor)
        self.record_answer()


def main():
    parser = argparse.ArgumentParser(description="Process test messages using Elroy API")
    parser.add_argument("input_file", help="Path to the input JSON file containing messages", default="data/longmemeval_s.json")
    parser.add_argument(
        "run_token",
        nargs="?",
        default=None,
        help="Optional prefix for user tokens. If not provided, a timestamp-based prefix will be generated.",
    )

    parser.parse_args()

    db_url = "sqlite:///elroy.db"

    engine = create_engine(db_url)
    with Session(engine) as session:
        questions = get_questions(session)
        for q in tqdm(questions, desc="Questions", position=0, leave=False):
            evaluator = QuestionEvaluator(session, db_url, q.question_id)
            evaluator.run()


if __name__ == "__main__":
    main()
