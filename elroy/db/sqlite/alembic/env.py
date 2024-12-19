import logging
import os
from functools import partial
from logging.config import fileConfig

from alembic import context
from toolz import pipe
from toolz.curried import keymap

from elroy.config.paths import get_default_sqlite_url
from elroy.db.migrate import run_migrations_offline, run_migrations_online

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
        lambda x: x.get("database_url") or os.environ.get("ELROY_DATABASE_URL") or get_default_sqlite_url(),
        str,
        lambda x: x if x.startswith("sqlite:///") else "sqlite:///" + x,
        partial(config.set_main_option, "sqlalchemy.url"),
    )

if context.is_offline_mode():
    run_migrations_offline(context, config)
else:
    run_migrations_online(context, config)
