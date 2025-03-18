from typing import Any, Callable

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from ..core.constants import allow_unused


@allow_unused
def run_migrations_offline(context, config, include_object: Callable[[Any, str, str, bool, Any], bool]) -> None:
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
        target_metadata=SQLModel.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


@allow_unused
def run_migrations_online(context, config, include_object: Callable[[Any, str, str, bool, Any], bool]) -> None:
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
        context.configure(
            connection=connection,
            target_metadata=SQLModel.metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()
