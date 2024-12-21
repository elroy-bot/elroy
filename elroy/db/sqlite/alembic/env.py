import os
from functools import partial
from logging.config import fileConfig
from operator import add

from alembic import context
from toolz import pipe
from toolz.curried import keymap

from elroy.config.paths import get_default_sqlite_path
from elroy.db.migrate import run_migrations_offline, run_migrations_online

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add command line option for postgres URL
sqlite_path = pipe(
    context.get_x_argument(as_dictionary=True),
    keymap(str.lower),
    keymap(lambda x: x.replace("-", "_")),
    lambda x: x.get("sqlite_path") or os.environ.get("ELROY_SQLITE_PATH") or get_default_sqlite_path(),
    partial(add, "sqlite:///"),
    partial(config.set_main_option, "sqlalchemy.url"),
)

if context.is_offline_mode():
    run_migrations_offline(context, config)
else:
    run_migrations_online(context, config)
