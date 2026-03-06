import logging
import os
from functools import partial
from logging.config import fileConfig

from alembic import context
from toolz import pipe
from toolz.curried import filter, keymap, map

from elroy.config.paths import get_default_sqlite_url
from elroy.db.migrate import run_migrations_offline, run_migrations_online
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
    database_path = pipe(
        context.get_x_argument(as_dictionary=True),
        keymap(str.lower),
        keymap(lambda x: x.replace("-", "_")),
        lambda x: [x.get("database_url"), os.environ.get("ELROY_DATABASE_URL"), get_default_sqlite_url()],
        filter(lambda x: x is not None),
        map(str),
        filter(lambda url: url.startswith("sqlite:///")),
        first_or_none,
        partial(config.set_main_option, "sqlalchemy.url"),
    )


def include_object(object, name, type_, reflected, compare_to):
    # Ignore all vectorstorage_* tables (managed by ChromaDB, not SQLAlchemy)
    return not (type_ == "table" and name.startswith("vectorstorage"))


if context.is_offline_mode():
    run_migrations_offline(context, config, include_object)
else:
    run_migrations_online(context, config, include_object)
