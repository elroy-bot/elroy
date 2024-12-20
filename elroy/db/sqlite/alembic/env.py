import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

### Imports necessary to correctly load SQLModel subclasses and set env variables ###
from ....repository import data_models

models = data_models

### End ####


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
from ....config.paths import get_default_sqlite_db_path

# Add command line option for postgres URL
cmd_opts = context.get_x_argument(as_dictionary=True)
if "sqlite-path" in cmd_opts:
    config.set_main_option("sqlalchemy.url", cmd_opts["sqlite-path"])
# Fall back to environment variable if no command line option
elif "ELROY_SQLITE_PATH" in os.environ:
    config.set_main_option("sqlalchemy.url", os.environ["ELROY_SQLITE_PATH"])
else:
    config.set_main_option("sqlalchemy.url", get_default_sqlite_db_path())

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
