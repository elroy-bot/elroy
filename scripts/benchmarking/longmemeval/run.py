#!/usr/bin/env python3

"""
Script to process test messages from an input JSON file using Elroy API.
The script simulates chat logs by recording messages and creating memories periodically.

This version uses Celery to distribute the workload across multiple containers:
- One container enqueues jobs to the Celery queue
- Other containers work on those jobs
"""

import argparse
import logging
import os
import socket
import sys
import time
from datetime import datetime
from random import shuffle
from typing import Callable, List

from freezegun import freeze_time
from litellm import completion
from openinference.instrumentation import using_metadata, using_session, using_user
from phoenix.trace import suppress_tracing
from smolagents import LiteLLMModel, Tool, ToolCallingAgent
from toolz import pipe
from toolz.curried import filter, remove

from elroy.core.session import dbsession
from elroy.messenger.error_recovery import retry_completion_api_return
from elroy.repository.memories.tools import examine_memories

# Add the current directory to the path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import logging
import sys

from benchmarking_db import (
    ChatMessage,
    ChatSession,
    Cursor,
    Question,
    do_load_data,
    get_answer_if_exists,
    get_assistant_has_answer_session_ids,
    get_messages_for_session,
    get_or_create_cursor,
    get_questions,
    get_sessions_for_question,
    init_db,
    update_or_create_answer,
)
from sqlmodel import Session

from elroy.api import Elroy
from elroy.core.constants import SYSTEM, USER
from elroy.core.tracing import tracer

# Configure root logger to output to stdout
logging.basicConfig(
    level=logging.INFO,  # Set appropriate level
    format="%(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Get a logger for this module
logger = logging.getLogger("benchmark")
logger.setLevel(logging.INFO)  # Adjust level as needed

hostname = socket.gethostname()

# Determine if this container should enqueue jobs or work on them
IS_ENQUEUER = os.environ.get("ELROY_BENCHMARK_ROLE", "worker") == "enqueuer"


def process_chat_session(
    msg_handler_func: Callable[[Elroy, ChatMessage], str],
    session: Session,
    cursor: Cursor,
    ai: Elroy,
    run_token: str,
    question_id: str,
    chat_session: ChatSession,
):
    with using_user(ai.token), using_session(chat_session.session_id):
        session_date = chat_session.session_date

        with freeze_time(datetime.strptime(session_date, "%Y/%m/%d (%a) %H:%M")):
            with suppress_tracing():
                ai.record_message(SYSTEM, f"The user has initiated a chat session. The current time is: {session_date}")
            # Get all messages for this session
            messages = get_messages_for_session(session, question_id, chat_session.session_id)

            for message_idx, message in enumerate(messages):
                if cursor.message_idx > message_idx:
                    logger.info(f"{cursor.method} {cursor.message_idx} > message_idx {message_idx}, skipping")
                    # Skip messages we've already processed
                    continue
                else:
                    logger.info(f"message {message_idx+1}/{len(messages)} for session {chat_session.session_id}")
                    with using_metadata(
                        {
                            "run_id": run_token,
                            "session_id": chat_session.session_id,
                            "session_date": session_date,
                            "question_id": question_id,
                            "message_idx": message_idx,
                            "message_id": message.id,
                            "has_answer": message.has_answer,
                        }
                    ):
                        msg_handler_func(ai, message)

                        cursor.message_idx = message_idx
                        session.add(cursor)
                        session.commit()
                        session.refresh(cursor)
            with suppress_tracing():
                ai.context_refresh()


def ai_assistant_response_to_chat(
    ai: Elroy,
    chat_message: ChatMessage,
):
    if chat_message.role == USER and chat_message.has_answer:
        return ai.message(chat_message.content)
    else:
        with suppress_tracing():
            return ai.message(chat_message.content)


def harcoded_assistant_response_to_chat(ai: Elroy, chat_message: ChatMessage) -> str:
    with suppress_tracing():
        return ai.record_message(chat_message.role, chat_message.content) or "recorded"


@tracer.agent
def force_tool_answer(ai: Elroy, question: str) -> str:

    ai.message(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
        force_tool="examine_memories",
    )

    return ai.message(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
    )


@tracer.agent
def just_answer(ai: Elroy, question: str) -> str:
    return ai.message(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
    )


class ExamineMemoryTool(Tool):
    name = "examine_memories"
    description = """"Search through memories for the answer to a question.

    This function searches summarized memories and goals. Each memory also contains source information.

    If a retrieved memory is relevant but lacks detail to answer the question, use the get_source_content_for_memory tool. This can be useful in cases where broad information about a topic is provided, but more exact recollection is necessary."""
    inputs = {"question": {"type": "string", "description": "The question to search for the answer for in memories"}}
    output_type = "array"

    def __init__(self, ai: Elroy):
        self.ai = ai
        super().__init__()

    def forward(self, question: str):
        with dbsession(self.ai.ctx):
            return examine_memories(self.ai.ctx, question)


@tracer.agent
def smol_agent_answer(ai: Elroy, question: str) -> str:
    model = LiteLLMModel(
        model_id=ai.ctx.chat_model.name,
        api_base=ai.ctx.chat_model.api_base,
    )
    agent = ToolCallingAgent(tools=[ExamineMemoryTool(ai)], model=model)
    return agent.run(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
    )  # type: ignore


def process_question(
    db_url: str,
    calculate_answer_fns: List[Callable[[Elroy, str], str]],
    msg_handler_func: Callable[[Elroy, ChatMessage], str],
    messages_between_memory: int,
    session: Session,
    base_run_token: str,
    question: Question,
):
    msg_processor_method = "__".join(
        [
            "mbm",
            str(messages_between_memory),
            "msg_handler_func",
            msg_handler_func.__name__,
        ]
    )

    run_token = f"{base_run_token}__{msg_processor_method}"
    user_token = f"{run_token}__qid__{question.question_id}"

    ai = Elroy(
        token=user_token,
        database_url=db_url,
        check_db_migration=False,
        show_tool_calls=False,
        messages_between_memory=messages_between_memory,
    )

    cursor = get_or_create_cursor(session, run_token, question.question_id, msg_processor_method)
    chat_sessions = get_sessions_for_question(session, question.question_id)

    for session_idx, chat_session in enumerate(chat_sessions):
        if cursor.session_idx > session_idx:
            # Skip sessions we've already processed
            logger.info(f"{cursor.method} {cursor.session_idx} > session_idx {session_idx}, skipping")
            continue
        else:
            logger.info(f"{msg_processor_method} session {session_idx+1}/{len(chat_sessions)} for question {question.question_id}")
            with using_user(user_token), using_session(chat_session.session_id):

                session_date = chat_session.session_date

                with freeze_time(datetime.strptime(session_date, "%Y/%m/%d (%a) %H:%M")):
                    process_chat_session(msg_handler_func, session, cursor, ai, run_token, question.question_id, chat_session)
            cursor.session_idx += 1
            cursor.message_idx = -1
            session.commit()
            session.refresh(cursor)

    ai.reset_messages()
    try:
        with using_metadata(
            {
                "run_id": run_token,
                "question_id": question.question_id,
                "question_type": question.question_type,
                "answer": question.answer,
                "question_date": question.question_date,
                "answer_session_ids": question.answer_session_ids,
            }
        ):

            with freeze_time(datetime.strptime(question.question_date, "%Y/%m/%d (%a) %H:%M")):
                ai.ctx.show_internal_thought = False

                for calculate_answer_fn in calculate_answer_fns:
                    method_desc = msg_processor_method + f"__calc_ans_fn__{calculate_answer_fn.__name__}"
                    elroy_answer = calculate_answer_fn(ai, question.question)
                    update_or_create_answer(
                        session,
                        run_token,
                        question.question_id,
                        question.question_type,
                        question=question.question,
                        elroy_answer=elroy_answer,
                        answer=question.answer,
                        answer_session_ids=question.answer_session_ids,
                        method=method_desc,
                    )

                    eval_answer(
                        session,
                        run_token,
                        question.question_id,
                        method_desc,
                    )
    finally:
        ai.ctx.show_internal_thought = True


@retry_completion_api_return
def eval_answer(session: Session, run_token: str, question_id: str, method: str) -> None:
    # via https://github.com/xiaowu0162/LongMemEval/blob/main/src/evaluation/evaluate_qa.py#L20

    answer_row = get_answer_if_exists(session, run_token, question_id, method)
    if not answer_row:
        logger.info(f"No answer found for {run_token} and {question_id}")
        return

    abstention = question_id.endswith("_abs")
    task = answer_row.question_type
    question = answer_row.question
    response = answer_row.elroy_answer
    answer = answer_row.answer

    if not abstention:
        if task in ["single-session-user", "single-session-assistant", "multi-session"]:
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        elif task == "temporal-reasoning":
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. In addition, do not penalize off-by-one errors for the number of days. If the question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the model's response is still correct. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        elif task == "knowledge-update":
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated answer, the response should be considered as correct as long as the updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        elif task == "single-session-preference":
            template = "I will give you a question, a rubric for desired personalized response, and a response from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model does not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes the user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        else:
            raise NotImplementedError
    else:
        template = "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if the model correctly identifies the question as unanswerable. The model could say that the information is incomplete, or some other information is given but the asked information is not.\n\nQuestion: {}\n\nExplanation: {}\n\nModel Response: {}\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only."
        prompt = template.format(question, answer, response)

    resp: str = (
        completion(
            model=os.environ["ELROY_BENCHMARK_JUDGE_MODEL"],
            messages=[{"role": USER, "content": prompt}],
            temperature=0,
            max_tokens=10,
            stream=False,
        )
        .choices[0]  # type: ignore
        .message.content.strip()  # type: ignore
    )  # type: ignore

    is_correct = "yes" in resp.lower()
    answer_row.is_correct = is_correct

    logger.info(f"Answer for question {question_id} is " + ("CORRECT" if is_correct else "INCORRECT"))
    answer_row.judge = os.environ["ELROY_BENCHMARK_JUDGE_MODEL"]
    session.add(answer_row)
    session.commit()


QUESTION_IDS = [
    "ce6d2d27",
    "e61a7584",
    "6a1eabeb",
    "7a87bd0c",
    "89941a93",
    "#dccbc061",
    "b01defab",
    "f685340e",
    "6a27ffc2",
]


def enqueue_jobs(db_url: str, input_file: str, run_token: str):
    """
    Enqueue jobs to the Celery queue.
    This function is called by the main function when IS_ENQUEUER is True.
    """
    try:
        # Import Celery tasks
        from celery_tasks import calculate_answer_task, process_chat_session_task
    except ImportError:
        logger.error("Failed to import Celery tasks. Make sure celery is installed.")
        sys.exit(1)

    engine = init_db(db_url)

    with Session(engine) as session:
        if len(get_questions(session)) == 0:
            do_load_data(session, db_url, input_file)

        assistant_answer_session_ids = get_assistant_has_answer_session_ids(session)

        questions = pipe(
            get_questions(session),
            remove(lambda q: q.question_type == "temporal-reasoning"),
            remove(lambda q: q.question_id.endswith("_abs")),
            remove(lambda q: set(q.answer_session_ids.split(", ")) & assistant_answer_session_ids),
            filter(lambda q: q.question_id in QUESTION_IDS),
            list,
        )

    logger.info(f"Enqueueing jobs for {len(questions)} questions")

    # Create a list of all tasks to enqueue
    tasks_to_enqueue = []

    for question in questions:
        for msg_handler_func in [harcoded_assistant_response_to_chat, ai_assistant_response_to_chat]:
            msg_handler_func_name = msg_handler_func.__name__

            # Create user token
            msg_processor_method = "__".join(
                [
                    "mbm",
                    str(20),  # messages_between_memory
                    "msg_handler_func",
                    msg_handler_func_name,
                ]
            )
            method_run_token = f"{run_token}__{msg_processor_method}"
            user_token = f"{method_run_token}__qid__{question.question_id}"

            # Get cursor
            cursor = get_or_create_cursor(session, method_run_token, question.question_id, msg_processor_method)

            # Get chat sessions
            chat_sessions = get_sessions_for_question(session, question.question_id)

            # Enqueue chat session tasks
            for session_idx, chat_session in enumerate(chat_sessions):
                if cursor.session_idx > session_idx:
                    # Skip sessions we've already processed
                    logger.info(f"{msg_processor_method} {cursor.session_idx} > session_idx {session_idx}, skipping")
                    continue

                # Enqueue task to process chat session
                tasks_to_enqueue.append(
                    {
                        "task": "process_chat_session",
                        "args": {
                            "msg_handler_func_name": msg_handler_func_name,
                            "session_id": session.id if hasattr(session, "id") else None,
                            "cursor_id": cursor.id,
                            "ai_token": user_token,
                            "db_url": db_url,
                            "run_token": method_run_token,
                            "question_id": question.question_id,
                            "chat_session_id": chat_session.session_id,
                            "messages_between_memory": 20,
                        },
                    }
                )

            # Enqueue tasks to calculate answers
            for calculate_answer_fn in [smol_agent_answer, force_tool_answer, just_answer]:
                calculate_answer_fn_name = calculate_answer_fn.__name__
                method_desc = msg_processor_method + f"__calc_ans_fn__{calculate_answer_fn_name}"

                tasks_to_enqueue.append(
                    {
                        "task": "calculate_answer",
                        "args": {
                            "calculate_answer_fn_name": calculate_answer_fn_name,
                            "db_url": db_url,
                            "user_token": user_token,
                            "run_token": method_run_token,
                            "question_id": question.question_id,
                            "question_type": question.question_type,
                            "question_text": question.question,
                            "answer": question.answer,
                            "answer_session_ids": question.answer_session_ids,
                            "method_desc": method_desc,
                            "messages_between_memory": 20,
                            "question_date": question.question_date,
                        },
                    }
                )

    # Shuffle tasks to distribute the workload
    shuffle(tasks_to_enqueue)

    # Enqueue tasks
    for idx, task_info in enumerate(tasks_to_enqueue):
        task_name = task_info["task"]
        task_args = task_info["args"]

        try:
            if task_name == "process_chat_session":
                process_chat_session_task.delay(**task_args)
            elif task_name == "calculate_answer":
                calculate_answer_task.delay(**task_args)

            logger.info(f"Enqueued task {idx + 1}/{len(tasks_to_enqueue)}: {task_name}")
        except Exception as e:
            logger.error(f"Failed to enqueue task {task_name}: {e}")

    logger.info(f"Enqueued {len(tasks_to_enqueue)} tasks")


def start_worker():
    """
    Start a Celery worker to process jobs from the queue.
    This function is called by the main function when IS_ENQUEUER is False.
    """
    try:
        from celery.bin import worker
        from celery_app import app
    except ImportError:
        logger.error("Failed to import Celery. Make sure celery is installed.")
        sys.exit(1)

    logger.info(f"Starting Celery worker on {hostname}")

    worker = worker.worker(app=app)
    worker.run(
        loglevel="INFO",
        traceback=True,
        hostname=f"worker@{hostname}",
    )


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

    if IS_ENQUEUER:
        # This container enqueues jobs
        logger.info(f"Running as enqueuer on {hostname}")
        enqueue_jobs(db_url, parsed.input_file, run_token)
    else:
        # This container works on jobs
        logger.info(f"Running as worker on {hostname}")
        start_worker()


if __name__ == "__main__":
    main()
