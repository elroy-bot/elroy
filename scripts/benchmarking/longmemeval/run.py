#!/usr/bin/env python3

"""
Script to process test messages from an input JSON file using Elroy API.
The script simulates chat logs by recording messages and creating memories periodically.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from functools import cached_property
from random import shuffle

from toolz import interleave, pipe
from toolz.curried import map

# Add the current directory to the path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from benchmarking_db import (
    ChatMessage,
    Question,
    do_load_data,
    get_messages_for_session,
    get_or_create_cursor,
    get_question_by_id,
    get_questions,
    get_sessions_for_question,
    init_db,
    update_or_create_answer,
)
from sqlmodel import Session, create_engine
from tqdm import tqdm

from elroy.api import Elroy
from elroy.core.constants import SYSTEM, USER
from elroy.core.tracing import tracer


class BenchmarkingQuestionRun:
    def __init__(self, session: Session, db_url: str, question_id: str, run_token: str):
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
            show_tool_calls=False,
        )

    @cached_property
    def question(self) -> Question:
        q = get_question_by_id(self.session, self.question_id)
        assert q
        return q

    @tracer.agent
    def ai_respond(self, msg: str) -> str:
        return self.ai.message(msg)

    def handle_msg(self, msg: ChatMessage):
        if msg.role == USER:
            return self.ai_respond(msg.content)

    @tracer.agent
    def record_answer(self, question_text: str, expected_answer: str) -> str:
        self.ai.reset_messages()

        try:
            self.ai.ctx.show_internal_thought = False

            elroy_answer = self.ai.message(
                f"""The following is a test of your memory.
                    Just give your answer, do not continue the conversation.
                    E.g. if the question is: What is 2+2? Respond simply with: 4.
                    Use tools to search for information!
                    If you don't know even after using tools, say if you don't know say I don't know.:
                    {self.question.question}"""
            )

            update_or_create_answer(
                self.session,
                self.run_token,
                self.question.question_id,
                self.question.question_type,
                question=self.question.question,
                elroy_answer=elroy_answer,
                answer=self.question.answer,
                answer_session_ids=self.question.answer_session_ids,
            )
        finally:
            self.ai.ctx.show_internal_thought = True
        return elroy_answer

    def run(self):
        from openinference.instrumentation import (
            using_metadata,
            using_session,
            using_user,
        )

        from elroy.utils.clock import FakeClock

        cursor = get_or_create_cursor(self.session, self.run_token, self.question_id)
        chat_sessions = get_sessions_for_question(self.session, self.question_id)

        for session_idx, chat_session in enumerate(tqdm(chat_sessions, desc="Sessions", position=1, leave=False)):
            if cursor.session_idx > session_idx:
                # Skip sessions we've already processed
                continue
            else:
                with using_user(self.user_token), using_session(chat_session.session_id):
                    session_date = chat_session.session_date
                    self.ai.ctx.clock = FakeClock(datetime.strptime(session_date, "%Y/%m/%d (%a) %H:%M"))

                    self.ai.record_message(SYSTEM, f"The user has initiated a chat session. The current time is: {session_date}")
                    # Get all messages for this session
                    messages = get_messages_for_session(self.session, self.question_id, chat_session.session_id)

                    for message_idx, message in enumerate(tqdm(messages, desc="Messages", position=2, leave=False)):
                        if cursor.message_idx > message_idx:
                            # Skip messages we've already processed
                            continue
                        else:
                            with using_metadata(
                                {
                                    "run_id": self.run_token,
                                    "session_id": chat_session.session_id,
                                    "session_date": session_date,
                                    "question_id": self.question_id,
                                    "message_idx": message_idx,
                                    "message_id": message.id,
                                    "has_answer": message.has_answer,
                                }
                            ):
                                self.handle_msg(message)

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
        with using_metadata(
            {
                "run_id": self.run_token,
                "question_id": self.question_id,
                "question_type": self.question.question_type,
                "answer": self.question.answer,
                "question_date": self.question.question_date,
                "answer_session_ids": self.question.answer_session_ids,
            }
        ):
            self.record_answer(self.question.question, self.question.answer)


class HardcodedAssistantResponseQRun(BenchmarkingQuestionRun):
    def __init__(self, session: Session, db_url: str, question_id: str, run_token: str, messages_between_memory: int = 20):
        self.session = session
        self.messages_between_memory = messages_between_memory
        self.db_url = db_url
        self.question_id = question_id
        self.run_token = f"msg_bt_mem_{messages_between_memory}_" + (run_token or f"run_{int(time.time())}")
        self.user_token = f"{self.run_token}_{self.question_id}"

    @cached_property
    def ai(self) -> Elroy:
        return Elroy(
            token=self.user_token,
            database_url=self.db_url,
            check_db_migration=False,
            show_tool_calls=False,
            messages_between_memory=self.messages_between_memory,
        )

    def handle_msg(self, msg: ChatMessage):
        return self.record_message(msg.role, msg.content)

    @tracer.agent
    def record_message(self, role: str, content: str):
        return self.ai.record_message(role, content)

    def should_handle_msg(self, msg: ChatMessage) -> bool:
        return msg.role == USER


def process_question(args: tuple[str, str, str, str]):
    eval_type, db_url, run_token, question_id = args
    engine = create_engine(db_url)
    with Session(engine) as session:
        if eval_type == "HardcodedAssistantResponseQRun":
            HardcodedAssistantResponseQRun(session, db_url, question_id, run_token).run()
        else:
            BenchmarkingQuestionRun(session, db_url, question_id, run_token).run()


def main():
    parser = argparse.ArgumentParser(description="Process test messages using Elroy API")
    parser.add_argument("input_file", help="Path to the input JSON file containing messages")
    parser.add_argument(
        "run_token",
        nargs="?",
        default=None,
        help="Optional prefix for user tokens. If not provided, a timestamp-based prefix will be generated.",
    )

    parsed = parser.parse_args()

    run_token = parsed.run_token or f"run_{int(time.time())}"

    db_url = os.environ["ELROY_BENCHMARK_DATABASE_URL"]

    engine = init_db(db_url)

    with Session(engine) as session:
        questions = get_questions(session)

        if len(questions) == 0:
            do_load_data(session, db_url, parsed.input_file)
            questions = get_questions(session)
        shuffle(questions)

    # Create interleaved functions using toolz
    func_args = pipe(
        [HardcodedAssistantResponseQRun, BenchmarkingQuestionRun],
        map(lambda eval_type: [[eval_type, db_url, run_token, q.question_id] for q in questions]),
        interleave,
        list,
    )
    shuffle(func_args)

    # Use imap to get a progress iterator
    for args in tqdm(func_args):
        process_question(args)


if __name__ == "__main__":
    main()
