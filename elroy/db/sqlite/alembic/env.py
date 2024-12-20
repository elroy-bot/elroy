import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel
from toolz import pipe
from toolz.curried import filter, keymap

### Imports necessary to correctly load SQLModel subclasses and set env variables ###
from ....repository import data_models

models = data_models

### End ####


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Add command line option for postgres URL
postgres_url = pipe(
    context.get_x_argument(as_dictionary=True),
    keymap(str.lower),
    keymap(lambda x: x.replace("-", "_")),
    lambda x: [x.get("postgres_url"), os.environ.get("ELROY_POSTGRES_URL")],
    filter(lambda x: x is not None),
    list,
    lambda x: x[0] if len(x) > 0 else None,
)

if not postgres_url:
    raise "No postgres URL provided: provide either via --postgres-url or via ELROY_POSTGRES_URL environment variable"

config.set_main_option("sqlalchemy.url", postgres_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()
