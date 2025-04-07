import logging
import os
from datetime import datetime
from typing import List, Optional, Set

from pytz import UTC
from sqlalchemy import create_engine
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, func, select, text

from elroy.core.constants import ASSISTANT


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

    __table_args__ = (UniqueConstraint("run_token", "question_id", "method"), {"extend_existing": True})

    id: Optional[int] = Field(default=None, primary_key=True)
    run_token: str
    question_id: str
    method: str
    session_idx: int = -1
    message_idx: int = -1
    is_complete: bool = False


class Answer(SQLModel, table=True):
    """Store benchmark answers"""

    __table_args__ = (UniqueConstraint("run_token", "question_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column_kwargs={"server_default": text("nextval('answer_id_seq'::regclass)")}
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    run_token: str
    question_id: str
    question_type: str
    question: str
    elroy_answer: str
    answer: str
    method: Optional[str] = None
    answer_session_ids: str
    is_correct: Optional[bool] = None
    judge: Optional[str] = None
    is_active: Optional[bool] = True


def get_db_url() -> str:
    """Get the database URL from the environment variable"""
    db_url = os.environ.get("ELROY_BENCHMARK_DATABASE_URL")
    if not db_url:
        raise ValueError("ELROY_BENCHMARK_DATABASE_URL environment variable is not set. Set to URL of sqlite or postgres db")
    return db_url


def get_engine():
    """Initialize the database tables"""
    engine = create_engine(get_db_url())
    SQLModel.metadata.create_all(engine, tables=[t.__table__ for t in [Question, ChatSession, ChatMessage, Cursor, Answer]])
    return engine


def get_assistant_has_answer_session_ids(session: Session) -> Set[str]:
    return set(
        session.exec(select(ChatMessage.session_id).where(ChatMessage.has_answer == True).where(ChatMessage.role == ASSISTANT)).all()
    )


def get_questions(session: Session) -> List[Question]:
    """Get all benchmark questions"""
    return list(session.exec(select(Question)))


def get_question(session: Session, question_id: str) -> Question:
    """Get a benchmark question by ID"""
    q = session.exec(select(Question).where(Question.question_id == question_id)).first()
    assert q
    return q


def get_or_create_cursor(session: Session, run_token: str, question_id: str, msg_processor_method: str) -> Cursor:
    """Get or create a cursor for tracking progress"""
    cursor = session.exec(
        select(Cursor)
        .where(Cursor.run_token == run_token)
        .where(Cursor.question_id == question_id)
        .where(Cursor.method == msg_processor_method)
    ).first()

    if not cursor:
        # Create new cursor entry
        cursor = Cursor(run_token=run_token, question_id=question_id, method=msg_processor_method, message_idx=0, session_idx=0)
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


def get_answer_if_exists(session: Session, run_token: str, question_id: str, method: str) -> Optional[Answer]:
    """Get an answer record by run token and question ID"""
    return session.exec(
        select(Answer)
        .where(Answer.run_token == run_token)
        .where(Answer.question_id == question_id)
        .where(Answer.is_active == True)
        .where(Answer.method == method)
    ).first()


def update_or_create_answer(
    session: Session,
    run_token: str,
    question_id: str,
    question_type: str,
    question: str,
    elroy_answer: str,
    answer: str,
    answer_session_ids: str,
    method: str,
) -> Answer:
    """Update or create an answer record"""
    existing_answer_row = get_answer_if_exists(session, run_token, question_id, method)

    if existing_answer_row:
        logging.info("Existing row found")
        if existing_answer_row.elroy_answer == elroy_answer:
            logging.info("Answer unchanged, returning existing answer")
            return existing_answer_row
        else:
            logging.info("Answer changed, marking old answer inactive")
            existing_answer_row.is_active = None
            session.add(existing_answer_row)
            session.commit()
            session.refresh(existing_answer_row)

    answer_row = Answer(
        run_token=run_token,
        question_id=question_id,
        question_type=question_type,
        question=question,
        elroy_answer=elroy_answer,
        answer=answer,
        answer_session_ids=answer_session_ids,
        method=method,
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


def get_messages_for_session(session: Session, session_id: str) -> List[ChatMessage]:
    """Get all messages for a chat session"""
    return list(
        session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.message_idx))  # type: ignore
    )  # type: ignore
