from dataclasses import dataclass
from datetime import datetime


@dataclass
class Question:
    longmemeval_question_id: str
    question: str
    question_date: datetime
    question_type: str
    answer: str


questions = [
    Question(
        "af082822",
        question_type="temporal-reasoning",
        question="How many weeks ago did I attend the friends and family sale at Nordstrom?",
        question_date=datetime.strptime("2022/12/01", "%Y/%m/%d"),
        answer="2",
    ),
    Question(
        "af082822",
        question_type="temporal-reasoning",
        question="On approximately what date did I purchase a new style pen?",
        question_date=datetime.strptime("2023/12/01", "%Y/%m/%d"),
        answer="Roughly 2022/11/01, give or take a few days.",
    ),
    Question(
        "af082822",
        question_type="temporal-reasoning",
        question="Approximately when did I move to Japan?",
        answer="Roughly 2022/05",
        question_date=datetime.strptime("2023/01/01", "%Y/%m/%d"),
    ),
    Question(
        "af082822",
        question_type="knowledge-update",
        question="How many sessions of the bereavement support group did I attend?",
        answer="Five",
        question_date=datetime.strptime("2023/11/07", "%Y/%m/%d"),
    ),
    Question(
        "af082822",
        question_type="knowledge-update",
        question="Who is Steven?",
        question_date=datetime.strptime("2022/11/14", "%Y/%m/%d"),
        answer="Steve is the user's ex-boyfriend.",
    ),
    Question(
        "af082822",
        question_type="multi-session-user",
        question="Who is Alex?",
        question_date=datetime.strptime("2023/11/14", "%Y/%m/%d"),
        answer="There are two people named Alex. One is the user's ex-boyfriend, and the other is a friend.",
    ),
    Question(
        "af082822",
        question_type="temporal-reasoning",
        answer="You have a stressful photoshoot today, with a difficult client.",
        question_date=datetime.strptime("2022/04/17", "%Y/%m/%d"),
        question="Why am I feeling stressed today?",
    ),
    Question(
        "ec81a493",
        question_type="single-session-user",
        question="How many copies of my favorite artist's debut album were released worldwide?",
        answer="500",
        question_date=datetime.strptime("2023/05/30", "%Y/%m/%d"),
    ),
    Question(
        "af082822",
        question_type="temporal-reasoning",
        question="How long did I know Alex before we started dating?",
        answer="Roughly two weeks",
        question_date=datetime.strptime("2022/06/17", "%Y/%m/%d"),
    ),
    Question(
        "af082822",
        question_type="temporal-reasoning",
        question="What caused Alex to break up with me?",
        answer="He didn not want to be in a long distance relationship after you moved to Japan.",
        question_date=datetime.strptime("2023/03/07", "%Y/%m/%d"),
    ),
    Question(
        "af082822",
        question_type="temporal-reasoning",
        question="What did the user buy on November 25",
        answer="Boots, a sweater, and a TV",
        question_date=datetime.strptime("2023/02/07", "%Y/%m/%d"),
    ),
]
