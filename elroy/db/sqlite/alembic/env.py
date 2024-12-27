import logging
import os
from functools import partial
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Engine, event
from toolz import pipe
from toolz.curried import filter, keymap, map

from elroy.config.paths import get_default_sqlite_url
from elroy.db.migrate import run_migrations_offline, run_migrations_online
from elroy.db.sqlite.sqlite_manager import SqliteManager
from elroy.utils.utils import first_or_none

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


database_path = config.get_main_option("sqlalchemy.url")

if database_path:
    logging.info("sqlite path found in config, using it for migration")
else:
    logging.info("sqlite path not found in config, retrieving from startup arguments")
    # Add command line option for postgres URL
    database_path = pipe(
        context.get_x_argument(as_dictionary=True),
        keymap(str.lower),
        keymap(lambda x: x.replace("-", "_")),
        lambda x: [x.get("database_url"), os.environ.get("ELROY_DATABASE_URL"), get_default_sqlite_url()],
        filter(lambda x: x is not None),
        map(str),
        filter(SqliteManager.is_valid_url),
        first_or_none,
        partial(config.set_main_option, "sqlalchemy.url"),
    )


# TODO: enable extension
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    import sqlite3

    import sqlite_vec

    # Only try to load extension for SQLite connections
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)


if context.is_offline_mode():
    run_migrations_offline(context, config)
else:
    run_migrations_online(context, config)
