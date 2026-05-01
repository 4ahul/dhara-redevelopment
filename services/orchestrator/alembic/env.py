import asyncio
import os
import sys

# Ensure repo root is on sys.path so absolute imports work in pre-deploy context
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import ONLY config and Base — avoid importing models or services packages,
# which trigger a circular import chain (models → db/__init__ → services → admin_service
# → services.orchestrator) that kills the pre-deploy migration.
# target_metadata=None is fine here: alembic upgrade head runs explicit DDL scripts
# and does not need metadata for comparison (that's only needed for autogenerate).
from services.orchestrator.core.config import settings
from services.orchestrator.db.base import Base

config = context.config

# Force the sqlalchemy.url from our application settings
config.set_main_option("sqlalchemy.url", settings.db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# For autogenerate support, populate this with all ORM models.
# Left as Base.metadata (empty — no models imported) for upgrade-only usage.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
