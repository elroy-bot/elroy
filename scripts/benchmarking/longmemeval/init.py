import argparse
import json

from sqlmodel import Session, func, select
from tqdm import tqdm

from db import ChatMessage, ChatSession, Question, get_db_url, get_engine
from elroy.api import Elroy


def main():
    parser = argparse.ArgumentParser(description="Initialize and manage the benchmarking database")
    parser.add_argument("--load-data", help="Path to the benchmark data JSON file to load")

    args = parser.parse_args()
    file_path = args.input_file

    try:
        print(f"Loading benchmark data from {file_path}...")
        with open(file_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"{file_path} is not a valid JSON file")
    except FileNotFoundError:
        raise FileNotFoundError(f"File {file_path} not found")

    with Session(get_engine()) as session:
        print(f"Importing {len(data)} questions into database...")
        # First check if data is already imported
        question_count = session.exec(select(func.count()).select_from(Question)).one()
        if question_count > 0:
            print("Data already exists in database. Skipping import.")
        else:
            # Import questions, sessions, and messages
            for item in tqdm(data, desc="Questions", position=0, leave=False):
                # Add question
                question = Question(
                    question_id=item["question_id"],
                    question_type=item["question_type"],
                    question=item["question"],
                    answer=item["answer"],
                    question_date=item["question_date"],
                    haystack_session_ids=", ".join(item["haystack_session_ids"]),
                    answer_session_ids=", ".join(item["answer_session_ids"]),
                )
                session.add(question)

                # Add chat sessions and messages
                for idx, session_id in enumerate(item["haystack_session_ids"]):
                    # Determine if this is an answer session
                    is_answer = session_id in item["answer_session_ids"]

                    # Get session date
                    session_date = item["haystack_dates"][idx] if idx < len(item["haystack_dates"]) else "unknown"

                    # Add chat session
                    chat_session = ChatSession(session_id=session_id, session_date=session_date, is_answer_session=is_answer)
                    session.add(chat_session)

                    # Add messages for this session
                    if idx < len(item["haystack_sessions"]):
                        for msg_idx, msg in enumerate(item["haystack_sessions"][idx]):
                            existing_row = session.exec(
                                select(ChatMessage).where(ChatMessage.session_id == session_id).where(ChatMessage.message_idx == msg_idx)
                            ).first()
                            if existing_row:
                                continue
                            else:
                                has_answer = "has_answer" in msg and msg["has_answer"]
                                chat_message = ChatMessage(
                                    session_id=session_id,
                                    message_idx=msg_idx,
                                    role=msg["role"],
                                    content=msg["content"],
                                    has_answer=has_answer,
                                )
                                session.add(chat_message)

            # Commit all changes
            session.commit()
            print("Data import complete.")
    ai = Elroy(database_url=get_db_url(), check_db_migration=True)
    ai.message("hello world")


if __name__ == "__main__":
    main()
