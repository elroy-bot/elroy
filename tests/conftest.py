import uuid
from collections.abc import Generator
from typing import Any, cast

import pytest
from sqlmodel import delete, select
from toolz import pipe
from toolz.curried import do

from elroy.cli.chat import onboard_non_interactive
from elroy.cli.options import resolve_model_alias
from elroy.core.constants import ASSISTANT, USER, allow_unused
from elroy.core.ctx import ElroyConfig
from elroy.core.session import open_turn_context
from elroy.db.db_manager import DbManager
from elroy.db.db_models import (
    AgendaItem,
    ContextMessageSet,
    Memory,
    Message,
    User,
    UserPreference,
)
from elroy.db.db_session import DbSession
from elroy.io.formatters.rich_formatter import RichFormatter
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.factory import build_context_refresh_orchestrator
from elroy.repository.context_messages.session import build_context_message_session
from elroy.repository.reminders.factory import build_reminder_orchestrator
from elroy.repository.user.store import create_user_id
from tests.utils import TEST_EMBEDDING_QUERIES, MockCliIO, MockLlmClient, _match_score

TEST_EMBEDDINGS: dict[str, dict[str, dict[str, Any]]] = {}


def _mock_query_vector(self: DbSession, l2_distance_threshold: float, table, user_id: int, query: list[float]):
    del l2_distance_threshold
    query_text = TEST_EMBEDDING_QUERIES.get(self.url, {}).get(tuple(query), "")
    rows = list(self.exec(select(table).where(table.user_id == user_id, table.is_active.is_(True))).all())

    def _row_text(row) -> str:
        if isinstance(row, Memory):
            return row.to_fact()
        if isinstance(row, AgendaItem):
            return row.to_fact()
        return str(row)

    ranked = sorted(rows, key=lambda row: _match_score(query_text, _row_text(row)), reverse=True)
    return [row for row in ranked if _match_score(query_text, _row_text(row)) > 0]


def _embedding_store(url: str) -> dict[str, dict[str, Any]]:
    return TEST_EMBEDDINGS.setdefault(url, {})


def _mock_insert_embedding(self: DbSession, row, embedding_data: list[float], embedding_text_md5: str):
    if row.id is None:
        raise ValueError("Cannot insert embedding for row without ID")
    _embedding_store(self.url)[self._doc_id(row)] = {
        "embedding": list(embedding_data),
        "embedding_text_md5": embedding_text_md5,
        "is_active": bool(row.is_active) if row.is_active is not None else False,
    }


def _mock_update_embedding(self: DbSession, row, embedding: list[float], embedding_text_md5: str):
    if row.id is None:
        raise ValueError("Cannot update embedding for row without ID")
    _embedding_store(self.url)[self._doc_id(row)] = {
        "embedding": list(embedding),
        "embedding_text_md5": embedding_text_md5,
        "is_active": bool(row.is_active) if row.is_active is not None else False,
    }


def _mock_get_embedding(self: DbSession, row) -> list[float] | None:
    if row.id is None:
        return None
    record = _embedding_store(self.url).get(self._doc_id(row))
    if record is None:
        return None
    return cast(list[float], record["embedding"])


def _mock_get_embedding_text_md5(self: DbSession, row) -> str | None:
    if row.id is None:
        return None
    record = _embedding_store(self.url).get(self._doc_id(row))
    if record is None:
        return None
    return cast(str | None, record["embedding_text_md5"])


def _mock_update_embedding_active(self: DbSession, row) -> None:
    if row.id is None:
        return
    record = _embedding_store(self.url).get(self._doc_id(row))
    if record is not None:
        record["is_active"] = bool(row.is_active) if row.is_active is not None else False


BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME = "Remember to follow through on basketball shots"


@allow_unused
def pytest_addoption(parser):
    parser.addoption(
        "--chat-models",
        action="store",
        default="gpt-5-nano",
        help="Comma-separated list of chat models to test",
    )


@allow_unused
def pytest_generate_tests(metafunc):
    if "chat_model_name" in metafunc.fixturenames:
        models = [resolve_model_alias(m) or m for m in metafunc.config.getoption("--chat-models").split(",")]
        metafunc.parametrize("chat_model_name", models, scope="session")


@pytest.fixture(scope="session")
def db_manager(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    url = pipe(
        data_dir,
        do(lambda x: x.mkdir(exist_ok=True)),
        lambda x: f"sqlite:///{x}/test.db",
    )
    db_manager = DbManager(url, chroma_path=data_dir / "chroma")

    db_manager.migrate()

    with db_manager.open_session() as db:
        for table in [Message, AgendaItem, User, UserPreference, Memory, ContextMessageSet]:
            db.exec(delete(table))
        db.commit()

    yield db_manager


@pytest.fixture(scope="session")
def db_session(db_manager: DbManager) -> Generator[DbSession, None, None]:
    with db_manager.open_session() as db:
        yield db


@pytest.fixture(scope="function")
def user_id(db_session, user_token) -> Generator[int, Any, None]:
    yield create_user_id(db_session, user_token)


@pytest.fixture(scope="function")
def io(rich_formatter: RichFormatter) -> Generator[MockCliIO, Any, None]:
    yield MockCliIO(rich_formatter)


@pytest.fixture(scope="function")
def george_ctx(ctx: ElroyConfig) -> Generator[ElroyConfig, Any, None]:
    messages = [
        ContextMessage(
            role=USER,
            content="Hello! My name is George. I'm curious about the history of Minnesota. Can you tell me about it?",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="Hello George! It's nice to meet you. I'd be happy to share some information about the history of Minnesota with you. What aspect of Minnesota's history are you most interested in?",
            chat_model=None,
        ),
        ContextMessage(
            role=USER,
            content="I'm particularly interested in when Minnesota became a state and any significant events leading up to that.",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="Certainly, George! Minnesota became the 32nd state of the United States on May 11, 1858. Here are some key events leading up to statehood:\n\n1. In 1803, the eastern part of Minnesota was acquired by the U.S. as part of the Louisiana Purchase.\n2. The western part was acquired in 1818 through a convention with Britain.\n3. In 1820, Fort Snelling was established at the confluence of the Mississippi and Minnesota rivers.\n4. The Minnesota Territory was created in 1849, which set the stage for eventual statehood.\n5. The population grew rapidly in the 1850s, leading to the push for statehood.\n\nWould you like to know more about any specific aspect of this period?",
            chat_model=None,
        ),
        ContextMessage(
            role=USER,
            content="That's interesting! What were some of the main industries or economic activities in Minnesota during its early statehood?",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="Great question, George! In its early years of statehood, Minnesota's economy was primarily based on natural resources and agriculture. Here are some key industries:\n\n1. Lumber: The vast forests in northern Minnesota made lumber a major industry.\n2. Agriculture: Wheat farming was particularly important, with Minneapolis becoming a major flour milling center.\n3. Iron ore mining: The discovery of iron ore in the Mesabi Range in the 1860s led to significant mining operations.\n4. Fur trading: While declining by the time of statehood, it had been a crucial early industry.\n5. Transportation: The Mississippi River and later railroads were vital for moving goods and people.\n\nThese industries shaped Minnesota's early development and laid the foundation for its future growth. Is there a particular industry you'd like to know more about?",
            chat_model=None,
        ),
        ContextMessage(
            role=USER,
            content="The iron ore mining sounds fascinating. Can you tell me more about the Mesabi Range and its impact on Minnesota?",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="Absolutely, George! The Mesabi Range and its iron ore mining had a profound impact on Minnesota. Here are some key points:\n\n1. Discovery: Iron ore was discovered in the Mesabi Range in 1866, but large-scale mining didn't begin until the 1890s.\n\n2. Location: The Mesabi Range is located in northeast Minnesota and is about 110 miles long and 1-3 miles wide.\n\n3. Economic impact: It became one of the world's largest iron ore mining districts, significantly boosting Minnesota's economy.\n\n4. Steel industry: The high-quality iron ore from the Mesabi Range was crucial for the U.S. steel industry, particularly during World Wars I and II.\n\n5. Technology: The development of open-pit mining and new transportation methods revolutionized the industry.\n\n6. Communities: Mining led to the growth of many towns in northern Minnesota, like Hibbing and Virginia.\n\n7. Environmental impact: While economically beneficial, mining also had significant environmental effects that are still being addressed today.\n\n8. Legacy: Although production has decreased since its peak, mining remains an important part of Minnesota's economy and identity.\n\nIs there a specific aspect of the Mesabi Range or iron mining you'd like to explore further?",
            chat_model=None,
        ),
        ContextMessage(
            role=USER,
            content="Thanks for all this information! It's really helped me understand Minnesota's history better.",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="You're welcome, George! I'm glad I could help you learn more about Minnesota's history, particularly about its statehood and the significant impact of iron ore mining in the Mesabi Range. Minnesota has a rich and diverse history that has shaped its culture and economy to this day. If you have any more questions about Minnesota or any other topic, feel free to ask. It's always a pleasure to explore history and share knowledge!",
            chat_model=None,
        ),
    ]

    with open_turn_context(ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).add_context_messages(messages)

        reminder_orchestrator = build_reminder_orchestrator(turn)
        reminder_orchestrator.do_create_due_item(
            BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME,
            "Remind Goerge to follow through if he mentions basketball.",
            None,
            "Whenever George mentions basketball",
        )

        reminder_orchestrator.do_create_due_item(
            "Pay off car loan by end of year",
            "Remind George to pay off his loan by the end of the year.",
            None,
            "when george mentions bills",
        )

    yield ctx


@pytest.fixture(scope="function")
def user_token() -> Generator[str, None, None]:
    yield str(uuid.uuid4())


@pytest.fixture(scope="function")
def ctx(db_manager: DbManager, db_session: DbSession, user_token, chat_model_name: str, tmp_path) -> Generator[ElroyConfig, None, None]:
    """Create an ElroyConfig for testing, using the same defaults as the CLI"""

    # Create new context with all parameters
    ctx = ElroyConfig.init(
        user_token=user_token,
        database_url=db_manager.url,
        chat_model=chat_model_name,
        use_background_threads=True,
        memory_dir=str(tmp_path / "memories"),
    )
    test_db_session = db_session
    cast(Any, test_db_session).query_vector = _mock_query_vector.__get__(test_db_session, DbSession)
    cast(Any, DbSession).query_vector = _mock_query_vector
    cast(Any, DbSession).insert_embedding = _mock_insert_embedding
    cast(Any, DbSession).update_embedding = _mock_update_embedding
    cast(Any, DbSession).get_embedding = _mock_get_embedding
    cast(Any, DbSession).get_embedding_text_md5 = _mock_get_embedding_text_md5
    cast(Any, DbSession).update_embedding_active = _mock_update_embedding_active
    TEST_EMBEDDING_QUERIES[db_manager.url] = {}
    TEST_EMBEDDINGS[db_manager.url] = {}
    ctx.__dict__["llm"] = MockLlmClient(ctx)
    ctx.__dict__["fast_llm"] = MockLlmClient(ctx)

    with open_turn_context(ctx) as turn:
        onboard_non_interactive(turn)
    yield ctx


@pytest.fixture(scope="session")
def rich_formatter():
    return RichFormatter(
        system_message_color="blue",
        assistant_message_color="green",
        user_input_color="red",
        warning_color="yellow",
        internal_thought_color="magenta",
    )
