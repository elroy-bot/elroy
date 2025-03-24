from typing import List, Optional

from sqlalchemy import create_engine
from sqlmodel import Field, Session, SQLModel, select


class Cursor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_token: str
    question_id: str
    session_idx: int = -1
    message_idx: int = -1
    is_complete: bool = False


class Answer(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
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


def get_or_create_cursor(session: Session, run_token: str, question_id: str):
    cursor = session.exec(select(Cursor).where(Cursor.run_token == run_token).where(Cursor.question_id == question_id)).first()

    if not cursor:
        # Create new cursor entry
        cursor = Cursor(run_token=run_token, question_id=question_id)
        session.add(cursor)

        session.commit()
    return cursor


def update_or_create_answer(
    session: Session,
    run_token: str,
    question_id: str,
    question_type: str,
    question: str,
    elroy_answer: str,
    answer: str,
    answer_session_ids: List[str],
):
    answer_row = session.exec(select(Answer).where(Answer.run_token == run_token).where(Answer.question_id == question_id)).first()

    if answer_row:
        answer_row.elroy_answer = elroy_answer
        answer_row.answer_session_ids = ", ".join(answer_session_ids)
    else:
        answer_row = Answer(
            run_token=run_token,
            question_id=question_id,
            question_type=question_type,
            question=question,
            elroy_answer=elroy_answer,
            answer=answer,
            answer_session_ids=", ".join(answer_session_ids),
        )
    session.add(answer_row)
    session.commit()
