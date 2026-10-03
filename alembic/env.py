"""
Alembic environment configuration for async SQLAlchemy + asyncpg.

Supports both offline (SQL script) and online (live DB) migration modes.
DATABASE_URL is read from app.config.settings so it respects the .env file.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import models so Alembic can detect schema changes ───────────────────────
from app.database import Base, get_async_database_url  # noqa: E402
from app.models.story import Story  # noqa: E402, F401  # registers model on Base

target_metadata = Base.metadata

# ── Override sqlalchemy.url from settings ─────────────────────────────────────
from app.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", get_async_database_url(settings.DATABASE_URL))


# ── Offline migrations ────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.
    Emits SQL to stdout; useful for review or DBA-managed deployment.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations ─────────────────────────────────────────────────────────

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations in an async context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — runs the async function via asyncio."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
