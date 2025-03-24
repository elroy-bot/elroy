import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy import create_engine
from sqlmodel import Field, Session, SQLModel, select


@dataclass
class BenchmarkQuestion:
    """Class representing a question from the LongMemEval dataset"""
    question_id: str
    question_type: str
    question: str
    answer: str
    question_date: str
    haystack_session_ids: List[str]
    haystack_dates: List[str]
    haystack_sessions: List[List[Dict[str, Any]]]
    answer_session_ids: List[str]


class BenchmarkDataset:
    """Class for loading and accessing the LongMemEval dataset"""
    
    # Class-level cache to store loaded datasets by file path
    _datasets_cache = {}
    
    def __init__(self, file_path: str):
        """
        Initialize the dataset from a JSON file
        
        Args:
            file_path: Path to the JSON file containing the dataset
        """
        self.file_path = file_path
        
        # Check if this dataset is already in the cache
        if file_path in BenchmarkDataset._datasets_cache:
            self.questions = BenchmarkDataset._datasets_cache[file_path]
        else:
            # Load the data and store in cache
            self.questions = self._load_data()
            BenchmarkDataset._datasets_cache[file_path] = self.questions
        
    def _load_data(self) -> List[BenchmarkQuestion]:
        """Load the dataset from the JSON file"""
        try:
            print(f"Loading benchmark data from {self.file_path}...")
            with open(self.file_path, "r") as f:
                data = json.load(f)
                return [BenchmarkQuestion(**item) for item in data]
        except json.JSONDecodeError:
            raise ValueError(f"{self.file_path} is not a valid JSON file")
        except FileNotFoundError:
            raise FileNotFoundError(f"File {self.file_path} not found")
            
    def get_question(self, question_id: str) -> Optional[BenchmarkQuestion]:
        """Get a question by its ID"""
        for question in self.questions:
            if question.question_id == question_id:
                return question
        return None
    
    def __len__(self) -> int:
        """Return the number of questions in the dataset"""
        return len(self.questions)
    
    def __getitem__(self, idx: int) -> BenchmarkQuestion:
        """Get a question by its index"""
        return self.questions[idx]


def load_benchmark_data(file_path: str) -> BenchmarkDataset:
    """
    Load the benchmark data from a JSON file
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        A BenchmarkDataset object
    """
    return BenchmarkDataset(file_path)


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


def check_run_exists(session: Session, run_token: str) -> bool:
    """
    Check if a run with the given token already exists in the database
    
    Args:
        session: SQLModel session
        run_token: The run token to check
        
    Returns:
        True if the run exists, False otherwise
    """
    cursor = session.exec(select(Cursor).where(Cursor.run_token == run_token)).first()
    return cursor is not None


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
        # Only update if the answer has changed
        if answer_row.elroy_answer != elroy_answer:
            answer_row.elroy_answer = elroy_answer
            answer_row.answer_session_ids = ", ".join(answer_session_ids)
            session.add(answer_row)
            session.commit()
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
