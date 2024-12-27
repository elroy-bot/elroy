import asyncio
import os
import subprocess
import uuid
from typing import Any, Generator

import click
import pytest
from sqlmodel import delete
from tests.utils import TestCliIO
from toolz import merge, pipe
from toolz.curried import do

from elroy.cli.config import onboard_user_non_interactive
from elroy.cli.options import get_config_params
from elroy.config.constants import ASSISTANT, USER
from elroy.config.ctx import ElroyContext
from elroy.db.db_manager import DbManager
from elroy.db.db_models import ContextMessageSet, Goal, Memory, User, UserPreference
from elroy.db.postgres.postgres_manager import PostgresManager
from elroy.db.sqlite.sqlite_manager import SqliteManager
from elroy.io.base import ElroyIO
from elroy.repository.goals.operations import create_goal
from elroy.repository.message import ContextMessage, Message, add_context_messages
from elroy.repository.user import create_user_id

ELROY_TEST_POSTGRES_URL = "ELROY_TEST_POSTGRES_URL"

BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME = "Remember to follow through on basketball shots"


def pytest_addoption(parser):
    parser.addoption("--postgres-url", action="store", default=None, help="Database URL from either environment or command line")
    parser.addoption(
        "--chat-models",
        action="store",
        default="gpt-4o-mini",
        help="Comma-separated list of chat models to test",
    )
    parser.addoption(
        "--db-type",
        action="store",
        default="sqlite",
        help="Database type to use for testing (postgres or sqlite)",
    )


@pytest.fixture(scope="session")
def postgres_url(request):
    if request.config.getoption("--postgres-url"):
        yield request.config.getoption("--postgres-url")
    elif ELROY_TEST_POSTGRES_URL in os.environ:
        yield os.environ[ELROY_TEST_POSTGRES_URL]
    elif not is_docker_running():
        raise Exception(
            f"Tests configured to run via PostGreSQL, but no PostGreSQL URL provided. Please either set the {ELROY_TEST_POSTGRES_URL} environment variable, provide a --postgres-url argument, or run tests with Docker."
        )
    else:
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("ankane/pgvector:v0.5.1") as postgres_container:
            postgres_host = postgres_container.get_container_host_ip()
            postgres_port = postgres_container.get_exposed_port(5432)
            yield f"postgresql://test:test@{postgres_host}:{postgres_port}/test"


def pytest_generate_tests(metafunc):
    if "chat_model_name" in metafunc.fixturenames:
        models = metafunc.config.getoption("--chat-models").split(",")
        metafunc.parametrize("chat_model_name", models, scope="session")
    if "db_type" in metafunc.fixturenames:
        db_types = metafunc.config.getoption("--db-type").split(",")
        metafunc.parametrize("db_type", db_types, scope="session")


@pytest.fixture(scope="session")
def db(
    request,
    tmp_path_factory,
    db_type: str,
):
    if db_type == "postgres":
        database_url = request.getfixturevalue("postgres_url")

        with PostgresManager.open_session(database_url, True) as db:
            for table in [Message, Goal, User, UserPreference, Memory, ContextMessageSet]:
                db.exec(delete(table))  # type: ignore
            db.commit()

            yield db
    else:
        url = pipe(tmp_path_factory.mktemp("data"), do(lambda x: x.mkdir(exist_ok=True)), lambda x: f"sqlite:///{x}/test.db")
        with SqliteManager.open_session(url, True) as db:
            for table in [Message, Goal, User, UserPreference, Memory, ContextMessageSet]:
                db.exec(delete(table))  # type: ignore
            db.commit()

            yield db


@pytest.fixture(scope="function")
def user_id(db, user_token) -> Generator[int, Any, None]:
    yield create_user_id(db, user_token)


@pytest.fixture(scope="function")
def io() -> Generator[ElroyIO, Any, None]:
    yield TestCliIO()


@pytest.fixture(scope="function")
def george_ctx(ctx: ElroyContext) -> Generator[ElroyContext, Any, None]:
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

    add_context_messages(ctx, messages)

    create_goal(
        ctx,
        BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME,
        "Remind Goerge to follow through if he mentions basketball.",
        "George is working to improve his basketball game, in particular his shooting form.",
        "George acknowledges my reminder that he needs to follow through on basketball shots.",
        "7 DAYS",
        0,
    )

    create_goal(
        ctx,
        "Pay off car loan by end of year",
        "Remind George to pay off his loan by the end of the year.",
        "George has a loan that he needs to pay off by the end of the year.",
        "George confirms that he has paid off his loan.",
        "1 YEAR",
        0,
    )

    yield ctx


@pytest.fixture(scope="function")
def user_token() -> Generator[str, None, None]:
    yield str(uuid.uuid4())


@pytest.fixture(scope="function")
def ctx(db: DbManager, user_token, chat_model_name: str) -> Generator[ElroyContext, None, None]:
    """Create an ElroyContext for testing, using the same defaults as the CLI"""

    params = get_config_params()

    params = merge(
        params,
        {
            "user_token": user_token,
            "config_file": None,
            "database_url": db.url,
            "chat_model": chat_model_name,
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY"),
            "tool": None,
        },
    )

    # Create new context with all parameters
    ctx = ElroyContext(command=click.Command("test"), **params)
    io = TestCliIO()
    ctx._io = io

    with ctx.with_db(db):
        asyncio.run(onboard_user_non_interactive(ctx))
        yield ctx


def is_docker_running():
    """Checks if docker daemon is running by trying to execute docker info"""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, check=True)
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
