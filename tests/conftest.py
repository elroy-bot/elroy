import asyncio
import inspect
import os
import subprocess
import uuid
from typing import Any, Generator

import pytest
from sqlmodel import delete, text
from tests.utils import TestCliIO
from toolz import keyfilter, merge, pipe
from toolz.curried import valfilter

from alembic.command import upgrade
from alembic.config import Config
from elroy import ROOT_DIR
from elroy.cli.config import init_elroy_context
from elroy.config.config import ElroyContext, get_config, load_defaults, session_manager
from elroy.io.base import ElroyIO
from elroy.repository.data_models import (
    ASSISTANT,
    USER,
    ContextMessageSet,
    Goal,
    Memory,
    User,
    UserPreference,
)
from elroy.repository.goals.operations import create_goal
from elroy.repository.message import ContextMessage, Message, add_context_messages
from elroy.repository.user import create_user_id

ELROY_TEST_POSTGRES_URL = "ELROY_TEST_POSTGRES_URL"

BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME = "Remember to follow through on basketball shots"


def pytest_addoption(parser):
    parser.addoption("--postgres-url", action="store", default=None, help="Database URL from either environment or command line")
    parser.addoption("--chat-models", action="store", default="gpt-4o", help="Comma-separated list of chat models to test")
    # parser.addoption("--chat-models", action="store", default="claude-3-5-sonnet-20241022", help="Comma-separated list of chat models to test")
    # TODO: Add multiple models once users have tokens associated with them (test isolation breaks, currently).
    # parser.addoption(
    # "--chat-models", action="store", default="gpt-4o,claude-3-5-sonnet-20241022", help="Comma-separated list of chat models to test"
    # )


def pytest_collection_modifyitems(items):
    """Automatically mark all test functions as asyncio."""
    for item in items:
        if item.get_closest_marker("asyncio") is None:
            item.add_marker(pytest.mark.asyncio)


@pytest.fixture(scope="function", autouse=True)
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_url(request):
    if request.config.getoption("--postgres-url"):
        yield request.config.getoption("--postgres-url")
    elif ELROY_TEST_POSTGRES_URL in os.environ:
        yield os.environ[ELROY_TEST_POSTGRES_URL]
    elif not is_docker_running():
        raise Exception(
            "By default, tests run using Docker containers for PostgreSQL."
            "To run tests without Docker, please provide a --postgres-url argument, "
            f"or set the {ELROY_TEST_POSTGRES_URL} environment variable."
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


@pytest.fixture(scope="session")
def elroy_config(postgres_url, chat_model_name):
    env_vars_dict = pipe(
        {
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "openai_organization": os.environ.get("OPENAI_ORGANIZATION"),
            "openai_api_base": os.environ.get("OPENAI_API_BASE"),
            "openai_embedding_api_base": os.environ.get("OPENAI_EMBEDDING_API_BASE"),
            "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY"),
        },
        valfilter(lambda x: x is not None),
    )

    yield pipe(
        load_defaults(),
        lambda x: merge(x, env_vars_dict, {"postgres_url": postgres_url, "chat_model_name": chat_model_name}),
        lambda x: keyfilter(lambda k: k in inspect.signature(get_config).parameters, x),
        lambda x: get_config(**x),
    )


@pytest.fixture(scope="session")
def session(elroy_config):
    with session_manager(elroy_config.postgres_url) as session:
        session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))  # type: ignore

    # apply migrations
    alembic_cfg = Config(os.path.join(ROOT_DIR, "alembic", "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", elroy_config.postgres_url)
    upgrade(alembic_cfg, "head")

    with session_manager(elroy_config.postgres_url) as session:
        for table in [Message, Goal, User, UserPreference, Memory, ContextMessageSet]:
            session.exec(delete(table))  # type: ignore
        session.commit()

        yield session


@pytest.fixture(scope="function")
def user_token(scope="function"):
    return str(uuid.uuid4())


@pytest.fixture(scope="function")
def user_id(session, user_token) -> Generator[int, Any, None]:
    yield create_user_id(session, user_token)


@pytest.fixture(scope="function")
def io() -> Generator[ElroyIO, Any, None]:
    yield TestCliIO()


@pytest.fixture(scope="function")
def elroy_context(session, user_token, io, elroy_config) -> Generator[ElroyContext, Any, None]:
    with init_elroy_context(session, elroy_config, io, user_token) as context:
        yield context


@pytest.fixture(scope="function")
def george_user_id(elroy_context) -> int:
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

    add_context_messages(elroy_context, messages)

    create_goal(
        elroy_context,
        BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME,
        "Remind Goerge to follow through if he mentions basketball.",
        "George is working to improve his basketball game, in particular his shooting form.",
        "George acknowledges my reminder that he needs to follow through on basketball shots.",
        "7 DAYS",
        0,
    )

    create_goal(
        elroy_context,
        "Pay off car loan by end of year",
        "Remind George to pay off his loan by the end of the year.",
        "George has a loan that he needs to pay off by the end of the year.",
        "George confirms that he has paid off his loan.",
        "1 YEAR",
        0,
    )

    return elroy_context.user_id


@pytest.fixture(scope="function")
def george_context(session, george_user_id, io, elroy_config) -> Generator[ElroyContext, None, None]:
    yield ElroyContext(
        session=session,
        user_id=george_user_id,
        io=io,
        config=elroy_config,
    )


def is_docker_running():
    """Checks if docker daemon is running by trying to execute docker info"""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, check=True)
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
