"""ORM 基类与公共 Mixin。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.types import BigIntVariant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """ORM 声明式基类。"""

    pass


class IDMixin:
    """自增主键。"""

    id: Mapped[int] = mapped_column(BigIntVariant(), primary_key=True, autoincrement=True)


class TenantMixin:
    """多租户隔离列。SQLite 单测靠 service 层过滤模拟 RLS。"""

    tenant_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)


class TimestampMixin:
    """创建/更新时间戳。"""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class SoftDeleteMixin:
    """软删除。"""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)


class VersionMixin:
    """乐观锁版本号。"""

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
