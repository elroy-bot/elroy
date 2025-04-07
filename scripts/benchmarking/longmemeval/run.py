#!/usr/bin/env python3

"""
Script to process test messages from an input JSON file using Elroy API.
The script simulates chat logs by recording messages and creating memories periodically.

This version uses Celery to distribute the workload across multiple containers:
- One container enqueues jobs to the Celery queue
- Other containers work on those jobs
"""

import logging
import os
import socket
import sys
from datetime import datetime
from typing import Callable

from celery import shared_task
from freezegun import freeze_time
from litellm import completion
from openinference.instrumentation import using_metadata, using_session, using_user

from elroy.messenger.error_recovery import retry_completion_api_return

# Add the current directory to the path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import logging
import sys

from answer_processors import ANSWER_FUNCS, get_answer_func
from enqueue import get_user_token
from message_processors import get_message_handler_func
from sqlmodel import Session

from db import (
    get_answer_if_exists,
    get_db_url,
    get_engine,
    get_messages_for_session,
    get_or_create_cursor,
    get_question,
    get_sessions_for_question,
    update_or_create_answer,
)
from elroy.api import Elroy
from elroy.core.constants import USER

MESSAGES_BETWEEN_MEMORY = 20

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


def get_ai(run_token: str, question_id: str, message_processor_func: Callable):
    return Elroy(
        token=get_user_token(run_token, question_id, message_processor_func),
        database_url=get_db_url(),
        check_db_migration=False,
        show_tool_calls=False,
        messages_between_memory=MESSAGES_BETWEEN_MEMORY,
    )


@shared_task(name="evaluate")
def evaluate(run_token: str, message_processor_name: str, answer_func_name: str, question_id: str):
    get_user_token(run_token, question_id, get_message_handler_func(message_processor_name))
    ai = get_ai(run_token, question_id, get_message_handler_func(message_processor_name))

    with Session(get_engine()) as session:
        question = get_question(session, question_id)

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

                calculate_answer_fn = get_answer_func(answer_func_name)

                method_desc = message_processor_name + f"__calc_ans_fn__{calculate_answer_fn.__name__}"
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


@shared_task(name="handle")
def handle(run_token: str, message_processor_name: str, question_id: str):

    msg_processor_func = get_message_handler_func(message_processor_name)
    user_token = get_user_token(run_token, question_id, msg_processor_func)
    with Session(get_engine()) as session:
        cursor = get_or_create_cursor(session, run_token, question_id, message_processor_name)
        logging.info(
            "Handling cursor: question_id: %s, run_token: %s, message_processor_name: %s", question_id, run_token, message_processor_name
        )

        session_idx, message_idx = cursor.session_idx, cursor.message_idx

        chat_sessions = get_sessions_for_question(session, question_id)
        if session_idx >= len(chat_sessions):
            for answer_func in ANSWER_FUNCS:
                evaluate(run_token, message_processor_name, answer_func.__name__, question_id)
            return

        chat_session = chat_sessions[session_idx]
        messages = get_messages_for_session(session, chat_session.session_id)
        if message_idx >= len(messages):
            cursor.session_idx += 1
            cursor.message_idx = 0
            session.commit()
            session.refresh(cursor)
            handle(run_token, message_processor_name, question_id)
            return

        message = messages[message_idx]
        ai = Elroy(
            token=user_token,
            database_url=get_db_url(),
            check_db_migration=False,
            show_tool_calls=False,
            messages_between_memory=MESSAGES_BETWEEN_MEMORY,
        )

        with using_user(user_token), using_session(chat_session.session_id):
            session_date = chat_session.session_date

            with freeze_time(datetime.strptime(session_date, "%Y/%m/%d (%a) %H:%M")):
                with using_metadata(
                    {
                        "run_id": run_token,
                        "message_processor_name": message_processor_name,
                        "session_id": chat_session.session_id,
                        "session_date": session_date,
                        "question_id": question_id,
                        "message_idx": message_idx,
                        "message_id": message.id,
                        "has_answer": message.has_answer,
                    }
                ):
                    msg_processor_func(ai, message)
                    cursor.message_idx += 1
                    session.add(cursor)
                    session.commit()
                    session.refresh(cursor)
                    handle.delay(run_token, message_processor_name, question_id)
                    return


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


def main():
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


if __name__ == "__main__":
    main()
