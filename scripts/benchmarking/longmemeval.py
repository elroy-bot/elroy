#!/usr/bin/env python3

"""
Script to process test messages from an input JSON file using Elroy API.
The script simulates chat logs by recording messages and creating memories periodically.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from elroy.api import Elroy


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
    db_dir = Path("./longmemeval_dbs")
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
    ai = Elroy(token=token_prefix + {question_id}, database_url=db_url)

    for session in data["haystack_sessions"]:
        for message in session:
            ai.record_message(message["role"], message["content"])

    ai_answer = ai.message(question)

    output = {"question_id": question_id, "question": question, "answer": answer, "ai_answer": ai_answer}

    # save to sqlite


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
