#!/usr/bin/env python3

"""
Celery tasks for the benchmarking setup.
This module defines the Celery tasks for processing benchmark jobs.
"""

import logging

# Import from local modules
from benchmarking_db import ChatSession, Cursor, update_or_create_answer
from celery import shared_task
from sqlmodel import Session

from elroy.api import Elroy

# Get a logger for this module
logger = logging.getLogger("benchmark_tasks")
logger.setLevel(logging.INFO)


@shared_task(name="process_chat_session")
def process_chat_session_task(
    msg_handler_func_name: str,
    session_id: str,
    cursor_id: str,
    ai_token: str,
    db_url: str,
    run_token: str,
    question_id: str,
    chat_session_id: str,
    messages_between_memory: int,
):
    """
    Celery task to process a chat session.
    This task is called by the run.py script to process a chat session.
    """
    from run import (
        ai_assistant_response_to_chat,
        harcoded_assistant_response_to_chat,
        process_chat_session,
    )

    # Map function names to actual functions
    msg_handler_funcs = {
        "ai_assistant_response_to_chat": ai_assistant_response_to_chat,
        "harcoded_assistant_response_to_chat": harcoded_assistant_response_to_chat,
    }

    msg_handler_func = msg_handler_funcs[msg_handler_func_name]

    # Initialize Elroy
    ai = Elroy(
        token=ai_token,
        database_url=db_url,
        check_db_migration=False,
        show_tool_calls=False,
        messages_between_memory=messages_between_memory,
    )

    # Get session and cursor
    from benchmarking_db import init_db

    engine = init_db(db_url)
    with Session(engine) as session:
        cursor = session.get(Cursor, cursor_id)
        chat_session = session.get(ChatSession, chat_session_id)

        # Process the chat session
        process_chat_session(msg_handler_func, session, cursor, ai, run_token, question_id, chat_session)

    return f"Processed chat session {chat_session_id} for question {question_id}"


@shared_task(name="calculate_answer")
def calculate_answer_task(
    calculate_answer_fn_name: str,
    db_url: str,
    user_token: str,
    run_token: str,
    question_id: str,
    question_type: str,
    question_text: str,
    answer: str,
    answer_session_ids: str,
    method_desc: str,
    messages_between_memory: int,
    question_date: str,
):
    """
    Celery task to calculate an answer for a question.
    This task is called by the run.py script to calculate an answer for a question.
    """
    from run import eval_answer, force_tool_answer, just_answer, smol_agent_answer

    # Map function names to actual functions
    calculate_answer_fns = {
        "force_tool_answer": force_tool_answer,
        "just_answer": just_answer,
        "smol_agent_answer": smol_agent_answer,
    }

    calculate_answer_fn = calculate_answer_fns[calculate_answer_fn_name]

    # Initialize Elroy
    ai = Elroy(
        token=user_token,
        database_url=db_url,
        check_db_migration=False,
        show_tool_calls=False,
        messages_between_memory=messages_between_memory,
    )

    # Reset messages
    ai.reset_messages()

    # Calculate answer
    from datetime import datetime

    from freezegun import freeze_time
    from openinference.instrumentation import using_metadata, using_user

    with (
        using_user(user_token),
        using_metadata(
            {
                "run_id": run_token,
                "question_id": question_id,
                "question_type": question_type,
                "answer": answer,
                "question_date": question_date,
                "answer_session_ids": answer_session_ids,
            }
        ),
    ):
        with freeze_time(datetime.strptime(question_date, "%Y/%m/%d (%a) %H:%M")):
            ai.ctx.show_internal_thought = False
            elroy_answer = calculate_answer_fn(ai, question_text)

    # Update or create answer
    from benchmarking_db import init_db

    engine = init_db(db_url)
    with Session(engine) as session:
        update_or_create_answer(
            session,
            run_token,
            question_id,
            question_type,
            question=question_text,
            elroy_answer=elroy_answer,
            answer=answer,
            answer_session_ids=answer_session_ids,
            method=method_desc,
        )

        # Evaluate answer
        eval_answer(
            session,
            run_token,
            question_id,
            method_desc,
        )

    return f"Calculated answer for question {question_id} using {calculate_answer_fn_name}"
