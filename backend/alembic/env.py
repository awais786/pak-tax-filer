"""Alembic environment (async), from Alembic's async template.

The database URL comes from the DATABASE_URL environment variable (set by docker-compose.yml),
never from alembic.ini, so no connection details are committed (research R3).
"""

# alembic.context is filled in by Alembic at run time, so pylint can't see its members, and
# `target_metadata` is the name Alembic's convention uses.
# pylint: disable=no-member,invalid-name

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set; docker-compose.yml sets it for the backend.")
config.set_main_option("sqlalchemy.url", database_url)

# No tables yet; feature 002 points this at the models' metadata for autogenerate.
target_metadata = None


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting (`alembic upgrade --sql`)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run the migrations on an open connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect with the async engine and run the migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
