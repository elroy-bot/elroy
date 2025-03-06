from dataclasses import dataclass
from datetime import datetime


@dataclass
class Question:
    question: str
    question_date: datetime
    question_type: str
    answer: str
    is_abstention: bool = False


QUESTIONS = sorted(
    [
        Question(
            question_type="temporal-reasoning",
            question="How many weeks ago did I attend the friends and family sale at Nordstrom?",
            question_date=datetime.strptime("2022/12/01", "%Y/%m/%d"),
            answer="2",
        ),
        Question(
            question_type="temporal-reasoning",
            question="On approximately what date did I purchase a new style pen?",
            question_date=datetime.strptime("2023/12/01", "%Y/%m/%d"),
            answer="Roughly 2022/11/01, give or take a few days.",
        ),
        Question(
            question_type="temporal-reasoning",
            question="Approximately when did I move to Japan?",
            answer="Roughly 2022/05",
            question_date=datetime.strptime("2023/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="How many sessions of the bereavement support group did I attend?",
            answer="Five",
            question_date=datetime.strptime("2023/11/07", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="Who is Steven?",
            question_date=datetime.strptime("2022/11/14", "%Y/%m/%d"),
            answer="Steve is the user's ex-boyfriend.",
        ),
        Question(
            question_type="multi-session-user",
            question="Who is Alex?",
            question_date=datetime.strptime("2023/11/14", "%Y/%m/%d"),
            answer="There are two people named Alex. One is the user's ex-boyfriend, and the other is a friend.",
        ),
        Question(
            question_type="temporal-reasoning",
            answer="You have a stressful photoshoot today, with a difficult client.",
            question_date=datetime.strptime("2023/04/17", "%Y/%m/%d"),
            question="Why am I feeling stressed today?",
        ),
        Question(
            question_type="single-session-user",
            question="How many copies of my favorite artist's debut album were released worldwide?",
            answer="500",
            question_date=datetime.strptime("2023/05/30", "%Y/%m/%d"),
        ),
        Question(
            question_type="temporal-reasoning",
            question="How long did I know Alex before we started dating?",
            answer="Roughly two weeks",
            question_date=datetime.strptime("2022/06/17", "%Y/%m/%d"),
        ),
        Question(
            question_type="temporal-reasoning",
            question="What caused Alex to break up with me?",
            answer="He didn not want to be in a long distance relationship after you moved to Japan.",
            question_date=datetime.strptime("2023/03/07", "%Y/%m/%d"),
        ),
        Question(
            question_type="temporal-reasoning",
            question="What did the user buy on November 25",
            answer="Boots, a sweater, and a TV",
            question_date=datetime.strptime("2023/02/07", "%Y/%m/%d"),
        ),
        Question(
            question="What company is Rachel, an old colleague from my previous company, currently working at?",
            question_type="knowledge-update",
            answer="TechCorp",
            question_date=datetime.strptime("2023/06/21 (Wed) 13:02", "%Y/%m/%d (%a) %H:%M"),
        ),
        Question(
            question_type="knowledge-update",
            question="What did the user consider buying to protect her camera, but ultimately did not?",
            answer="A lens cap, lens mount gaskets, lens mount seals.",
            question_date=datetime.strptime("2023/06/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="Why did user buy gifts from Target?",
            answer="She was happy about a good deal she got on earbuds",
            question_date=datetime.strptime("2023/07/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What store is the user likely to buy decorations from her home from?",
            answer="Target",
            question_date=datetime.strptime("2023/08/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What is the name of the user's close friend who moved away?",
            answer="Sarah",
            question_date=datetime.strptime("2023/06/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What is the name of the friend who the user caught up with in early March?",
            answer="Sandy",
            question_date=datetime.strptime("2023/06/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What did the user buy for Sandy?",
            answer="Ina Garten's cookbook, 'The Barefoot Contessa Cookbook'",
            question_date=datetime.strptime("2023/06/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What days of the week does the user ride the bus?",
            answer="Monday, Wednesday, and Friday",
            question_date=datetime.strptime("2023/08/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="Who does the user know with the name Rachel?",
            answer="A former work colleague, and a yoga teacher. A friend who the user lent photography equipment might be a third person.",
            question_date=datetime.strptime("2023/07/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What did the user use to track podcast episodes?",
            answer="Trello",
            question_date=datetime.strptime("2023/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What works of fiction did the user analyze from a gender perspective?",
            answer="Donnie Darko",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="Which of values is the user most passionate about? Economic equality, environmentalism, or religious freedom?",
            answer="Environmentalism",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What does the user like to do for exercise?",
            answer="Yoga",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What is the user's therapist's name?",
            answer="Dr. Smith",
            question_date=datetime.strptime("2023/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What is the user's relation to William?",
            answer="William is the user's nephew",
            question_date=datetime.strptime("2023/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="How does the user know Rosie?",
            answer="Rosie is the user's nephew's girlfriend",
            question_date=datetime.strptime("2023/03/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What health problem does the user and Rosie have in common?",
            answer="Both have dry skin",
            question_date=datetime.strptime("2023/06/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What was the user sad about in May?",
            answer="The user was sad about the death of her grandmother.",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="Who did the user create a will for?",
            answer="Rosalynn McClenagan",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What is the user more interested in, sports or music?",
            answer="Music",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What does the user dislike about ordering takeout?",
            answer="It generates too much plastic waste.",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What book is the user more likely to be interested in, 'The Handmaids Tale' or 'Blood Meridian'?",
            answer="The Handmaids Tale",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
        Question(
            question_type="knowledge-update",
            question="What kind of advertisement would likely appeal to the user more: one which touted convenience, or one which highlighted a limited time discount?",
            answer="One which highlighted a limited time discount.",
            question_date=datetime.strptime("2024/01/01", "%Y/%m/%d"),
        ),
    ],
    key=lambda x: x.question_date,
)
