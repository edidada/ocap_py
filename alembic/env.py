"""Alembic environment: async PG + metadata from app.db.base.Base.

Run:
    alembic revision --autogenerate -m "add xxx"
    alembic upgrade head
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 注意：必须导入所有 models 模块以确保 Base.metadata 被注册
from app.db.base import Base  # noqa: E402,F401
import app.domains.trigger.models  # noqa: E402,F401
import app.domains.workflow.models  # noqa: E402,F401
import app.domains.rca.models  # noqa: E402,F401
import app.domains.action.models  # noqa: E402,F401
import app.domains.integration.models  # noqa: E402,F401
import app.domains.knowledge.models  # noqa: E402,F401
import app.domains.analytics.models  # noqa: E402,F401
import app.domains.compliance.models  # noqa: E402,F401
import app.domains.iam.models  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 从环境变量覆盖 sqlalchemy.url（便于 CI/CD）
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)


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
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine and associate a connection with the context."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # 如果是 SQLite（DATABASE_URL 以 sqlite 开头），使用同步执行以避免 asyncpg 依赖
    url = config.get_main_option("sqlalchemy.url") or ""
    if url.startswith("sqlite"):
        from sqlalchemy import create_engine

        sync_conn = create_engine(url, poolclass=pool.NullPool)
        with sync_conn.connect() as c:
            do_run_migrations(c)
        sync_conn.dispose()
        return

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
