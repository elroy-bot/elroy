from typing import Optional

from sqlmodel import Field, SQLModel


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
