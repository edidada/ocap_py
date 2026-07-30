"""数据库会话管理。

engine 工厂化：生产用 PostgreSQL，单测用 SQLite 内存库（通过 dependency_overrides
覆盖 ``get_db``）。``create_async_engine`` 是惰性的，import 时不连接。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def create_async_engine_from_url(url: str, *, echo: bool | None = None, **kwargs) -> AsyncEngine:
    """按 URL 创建异步引擎；SQLite 不使用队列池。"""
    if url.startswith("sqlite"):
        return create_async_engine(url, echo=echo if echo is not None else settings.DEBUG, future=True)
    return create_async_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        echo=echo if echo is not None else settings.DEBUG,
        future=True,
    )


# 生产引擎（惰性，import 时不连接）
engine: AsyncEngine = create_async_engine_from_url(settings.async_database_url)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖（生产）。单测通过 dependency_overrides 替换。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
