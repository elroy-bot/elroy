#!/usr/bin/env python3
"""
Script to preprocess questions and haystack sessions for LongMemEval.
For each question, creates a directory with files for each haystack session.
"""

import json
import os
import argparse
from pathlib import Path
import re
from datetime import datetime


def create_directory(directory_path):
    """
    Create a directory if it doesn't exist.

    Args:
        directory_path (str): Path to the directory to create
    """
    os.makedirs(directory_path, exist_ok=True)


def format_date_for_sorting(date_str):
    """
    Convert date string to a format that can be used for sorting filenames.

    Args:
        date_str (str): Date string in format "YYYY/MM/DD (Day) HH:MM"

    Returns:
        str: Date string in format "YYYYMMDD_HHMM"
    """
    # Extract date and time using regex
    match = re.match(r"(\d{4})/(\d{2})/(\d{2}) \([A-Za-z]{3}\) (\d{2}):(\d{2})", date_str)
    if match:
        year, month, day, hour, minute = match.groups()
        return f"{year}{month}{day}_{hour}{minute}"
    return date_str.replace("/", "").replace(" ", "_").replace("(", "").replace(")", "").replace(":", "")


def preprocess_questions(data_file, output_dir):
    """
    Preprocess questions and haystack sessions.

    Args:
        data_file (str): Path to the JSON data file
        output_dir (str): Path to the output directory
    """
    # Read the data
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Processing {len(data)} questions...")

    # Create the base output directory if it doesn't exist
    create_directory(output_dir)

    # Process each question
    for question in data:
        question_id = question["question_id"]
        question_dir = os.path.join(output_dir, question_id)

        # Create directory for the question
        create_directory(question_dir)

        # Process each haystack session
        for i, (session_id, session_date, session) in enumerate(
            zip(question["haystack_session_ids"], question["haystack_dates"], question["haystack_sessions"])
        ):
            # Format date for sorting
            formatted_date = format_date_for_sorting(session_date)

            # Create filename that's sortable by date
            filename = f"{formatted_date}_{session_id}.txt"
            file_path = os.path.join(question_dir, filename)

            # Prepare the content with the session transcript header
            content = f"Session transcript from {session_date}\n\n"

            # Add each turn to the content
            for turn in session:
                role = turn["role"]
                message = turn["content"]
                content += f"{role.upper()}: {message}\n\n"

            # Write the content to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        print(f"Processed question {question_id} with {len(question['haystack_sessions'])} sessions")


def main():
    """Main function to parse arguments and process the data."""
    parser = argparse.ArgumentParser(description="Preprocess LongMemEval questions and haystack sessions")
    parser.add_argument(
        "--data_file", type=str, default="data/longmemeval_s.json", help="Path to the JSON data file (default: data/longmemeval_s.json)"
    )
    parser.add_argument(
        "--output_dir", type=str, default="data/question_data", help="Path to the output directory (default: data/question_data)"
    )

    args = parser.parse_args()

    # Ensure the data file exists
    if not os.path.exists(args.data_file):
        print(f"Error: File '{args.data_file}' not found.")
        return

    # Preprocess the questions
    preprocess_questions(args.data_file, args.output_dir)
    print(f"Preprocessing complete. Output directory: {args.output_dir}")


if __name__ == "__main__":
    main()
