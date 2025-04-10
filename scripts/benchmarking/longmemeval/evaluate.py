import logging
import os
from datetime import UTC, datetime
from typing import Callable, Optional

from attr import dataclass
from questions import Question
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

logger = logging.getLogger("evaluate")


class Answer(SQLModel, table=True):
    """Store benchmark answers"""

    __table_args__ = (UniqueConstraint("message_cursor_id", "question", "answer_fn"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    message_cursor_id: int
    answer_fn: str
    question_type: str
    question: str
    elroy_answer: str
    answer: str
    is_correct: Optional[bool] = None
    judge: Optional[str] = None


@dataclass
class EvalMethod:
    """Store benchmark evaluation methods"""

    name: str
    description: str
    message_fn: Callable
    answer_fn: Callable


class MessageCursor(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("token", "message_fn"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    token: str
    message_fn: str
    message_idx: int = Field(default=0)
    is_complete: bool = Field(default=False)


def get_db_url() -> str:
    """Get the database URL from the environment variable"""
    db_url = os.environ.get("ELROY_BENCHMARK_DATABASE_URL")
    if not db_url:
        raise ValueError("ELROY_BENCHMARK_DATABASE_URL environment variable is not set. Set to URL of sqlite or postgres db")
    return db_url


def get_engine():
    """Initialize the database tables"""
    engine = create_engine(get_db_url())
    SQLModel.metadata.create_all(engine, tables=[t.__table__ for t in [MessageCursor, Answer]])
    return engine


def get_or_create_message_cursor(session: Session, token: str, message_fn: Callable) -> MessageCursor:
    """Get or create a message cursor record"""

    existing_row = session.exec(
        select(MessageCursor).where(MessageCursor.token == token).where(MessageCursor.message_fn == message_fn.__name__)
    ).first()

    if existing_row:
        return existing_row
    else:
        message_cursor_row = MessageCursor(
            token=token,
            message_fn=message_fn.__name__,
        )
        session.add(message_cursor_row)
        session.commit()
        session.refresh(message_cursor_row)
        return message_cursor_row


def get_answer_if_exists(session: Session, message_cursor_id: int, question: Question, answer_fn: Callable) -> Optional[Answer]:
    """Get an answer record by run token and question ID"""
    return session.exec(
        select(Answer)
        .where(Answer.message_cursor_id == message_cursor_id)
        .where(Answer.question == question.question)
        .where(Answer.answer_fn == answer_fn.__name__)
    ).first()


def create_answer(
    session: Session, answer_fn: Callable, elroy_answer: str, question: Question, cursor_id: int, is_correct: bool, judge: str
) -> Optional[Answer]:
    """Update or create an answer record"""
    existing_answer_row = get_answer_if_exists(session, cursor_id, question, answer_fn)

    if existing_answer_row:
        logger.info(f"Answer already exists for cursor_id {cursor_id} and question {question}")
        return None

    answer_row = Answer(
        message_cursor_id=cursor_id,
        answer_fn=answer_fn.__name__,
        question_type=question.question_type,
        question=question.question,
        elroy_answer=elroy_answer,
        answer=question.answer,
        is_correct=is_correct,
        judge=judge,
    )

    session.add(answer_row)
    session.commit()
    session.refresh(answer_row)

    return answer_row
