import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, func, select
from tqdm import tqdm

from elroy.api import Elroy


# Database model classes
class Question(SQLModel, table=True):
    """Database model for benchmark questions"""

    __table_args__ = (UniqueConstraint("question_id"), {"extend_existing": True})

    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: str = Field(index=True)
    question_type: str
    question: str
    answer: str
    question_date: str
    haystack_session_ids: str
    answer_session_ids: str

    def __repr__(self):
        return f"Question(id={self.id}, question_id={self.question_id})"


class ChatSession(SQLModel, table=True):
    """Database model for chat sessions"""

    __table_args__ = (UniqueConstraint("session_id", "session_date"), {"extend_existing": True})

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    session_date: str
    is_answer_session: bool = False

    def __repr__(self):
        return f"ChatSession(id={self.id}, session_id={self.session_id})"


class ChatMessage(SQLModel, table=True):
    """Database model for chat messages within sessions"""

    __table_args__ = (UniqueConstraint("session_id", "message_idx"), {"extend_existing": True})

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    message_idx: int
    role: str
    content: str
    has_answer: bool = False

    def __repr__(self):
        return f"ChatMessage(id={self.id}, session_id={self.session_id}, message_idx={self.message_idx})"


class Cursor(SQLModel, table=True):
    """Cursor to track progress of benchmark runs"""

    __table_args__ = (UniqueConstraint("run_token", "question_id"), {"extend_existing": True})

    id: Optional[int] = Field(default=None, primary_key=True)
    run_token: str
    question_id: str
    session_idx: int = -1
    message_idx: int = -1
    is_complete: bool = False


class Answer(SQLModel, table=True):
    """Store benchmark answers"""

    __table_args__ = (UniqueConstraint("run_token", "question_id"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    run_token: str
    question_id: str
    question_type: str
    question: str
    elroy_answer: str
    answer: str
    answer_session_ids: str


def init_db(db_url: str):
    """Initialize the database tables"""
    engine = create_engine(db_url)
    SQLModel.metadata.create_all(engine)
    return engine


def load_benchmark_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load the benchmark data from a JSON file

    Args:
        file_path: Path to the JSON file

    Returns:
        List of question dictionaries
    """
    try:
        print(f"Loading benchmark data from {file_path}...")
        with open(file_path, "r") as f:
            data = json.load(f)
            return data
    except json.JSONDecodeError:
        raise ValueError(f"{file_path} is not a valid JSON file")
    except FileNotFoundError:
        raise FileNotFoundError(f"File {file_path} not found")


def import_benchmark_data(session: Session, data: List[Dict[str, Any]]) -> None:
    """
    Import benchmark data into the database

    Args:
        session: SQLModel session
        data: List of question dictionaries
    """

    print(f"Importing {len(data)} questions into database...")

    # First check if data is already imported
    question_count = session.exec(select(func.count()).select_from(Question)).one()
    if question_count > 0:
        print("Data already exists in database. Skipping import.")
        return

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


def get_questions(session: Session) -> List[Question]:
    """Get all benchmark questions"""
    return list(session.exec(select(Question)))


def get_or_create_cursor(session: Session, run_token: str, question_id: str) -> Cursor:
    """Get or create a cursor for tracking progress"""
    cursor = session.exec(select(Cursor).where(Cursor.run_token == run_token).where(Cursor.question_id == question_id)).first()

    if not cursor:
        # Create new cursor entry
        cursor = Cursor(run_token=run_token, question_id=question_id)
        session.add(cursor)
        session.commit()
        session.refresh(cursor)

    return cursor


def check_run_exists(session: Session, run_token: str) -> bool:
    """
    Check if a run with the given token already exists in the database

    Args:
        session: SQLModel session
        run_token: The run token to check

    Returns:
        True if the run exists, False otherwise
    """
    cursor_count = session.exec(select(func.count()).where(Cursor.run_token == run_token)).one()
    return cursor_count > 0


def update_or_create_answer(
    session: Session,
    run_token: str,
    question_id: str,
    question_type: str,
    question: str,
    elroy_answer: str,
    answer: str,
    answer_session_ids: str,
) -> Answer:
    """Update or create an answer record"""
    answer_row = session.exec(select(Answer).where(Answer.run_token == run_token).where(Answer.question_id == question_id)).first()

    if answer_row:
        # Only update if the answer has changed
        if answer_row.elroy_answer != elroy_answer:
            answer_row.elroy_answer = elroy_answer
            answer_row.answer_session_ids = answer_session_ids
            session.add(answer_row)
            session.commit()
            session.refresh(answer_row)
    else:
        answer_row = Answer(
            run_token=run_token,
            question_id=question_id,
            question_type=question_type,
            question=question,
            elroy_answer=elroy_answer,
            answer=answer,
            answer_session_ids=answer_session_ids,
        )
        session.add(answer_row)
        session.commit()
        session.refresh(answer_row)

    return answer_row


def get_question_by_id(session: Session, question_id: str) -> Optional[Question]:
    """Get a question by its ID"""
    return session.exec(select(Question).where(Question.question_id == question_id)).first()


def get_sessions_for_question(session: Session, question_id: str) -> List[ChatSession]:
    """Get all chat sessions for a question"""
    question = get_question_by_id(session, question_id)

    assert question

    session_ids = question.haystack_session_ids.split(", ")

    return list(session.exec(select(ChatSession).where(ChatSession.session_id.in_(session_ids)).order_by(ChatSession.session_date)))  # type: ignore


def get_messages_for_session(session: Session, question_id: str, session_id: str) -> List[ChatMessage]:
    """Get all messages for a chat session"""
    return list(
        session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.message_idx))  # type: ignore
    )  # type: ignore


def main():
    """
    Main function to initialize the database and print schema information
    when the script is run directly.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Initialize and manage the benchmarking database")
    parser.add_argument("--load-data", default="./data/longmemeval_s.json", help="Path to the benchmark data JSON file to load")

    args = parser.parse_args()

    if not os.environ.get("ELROY_BENCHMARK_DATABASE_URL"):
        raise ValueError("ELROY_BENCHMARK_DATABASE_URL environment variable is not set. Set to URL of sqlite or postgres db")
    db_url = os.environ["ELROY_BENCHMARK_DATABASE_URL"]

    if args.load_data:
        engine = init_db(db_url)
        with Session(engine) as session:
            data = load_benchmark_data(args.load_data)
            import_benchmark_data(session, data)
        ai = Elroy(database_url=db_url, check_db_migration=True)
        ai.message("hello world")


if __name__ == "__main__":
    main()
