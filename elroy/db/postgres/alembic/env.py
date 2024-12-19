import os
from functools import partial
from logging.config import fileConfig

from alembic import context
from toolz import pipe
from toolz.curried import do, keymap

from elroy.db.migrate import run_migrations_offline, run_migrations_online

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

database_url = config.get_main_option("sqlalchemy.url")

if not database_url:
    database_url = pipe(
        context.get_x_argument(as_dictionary=True),
        keymap(str.lower),
        keymap(lambda x: x.replace("-", "_")),
        lambda x: x.get("database_url") or os.environ.get("ELROY_DATABASE_URL"),
        do(partial(config.set_main_option, "sqlalchemy.url")),
    )

if not database_url:
    raise ValueError("No postgres URL provided: provide either via --database-url or via ELROY_DATABASE_URL environment variable")


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


if context.is_offline_mode():
    run_migrations_offline(context, config)
else:
    run_migrations_online(context, config)
