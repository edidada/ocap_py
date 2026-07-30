"""IAM 域 ORM 模型：租户、用户、角色、权限。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import BigIntVariant
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin
from app.domains.common.enums import RoleCode, TenantStatus


class Tenant(Base, IDMixin, TimestampMixin):
    __tablename__ = "tenants"
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TenantStatus.ACTIVE.value)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)


class Permission(Base, IDMixin):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    roles: Mapped[list[Role]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )


class Role(Base, IDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_role_tenant_code"),)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    users: Mapped[list[User]] = relationship(secondary="user_roles", back_populates="roles")
    permissions: Mapped[list[Permission]] = relationship(
        secondary="role_permissions", back_populates="roles"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class User(Base, IDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"),)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    roles: Mapped[list[Role]] = relationship(secondary="user_roles", back_populates="users")

    @property
    def role_codes(self) -> set[str]:
        return {r.code for r in self.roles}

    @property
    def permission_codes(self) -> set[str]:
        codes: set[str] = set()
        for role in self.roles:
            for perm in role.permissions:
                codes.add(perm.code)
        return codes


async def load_user_with_relations(db: AsyncSession, user_id: int) -> User | None:
    """加载用户及其角色、权限（避免懒加载在异步会话中报错）。"""
    stmt = (
        select(User)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        return None
    # 显式触发角色与权限加载
    await db.refresh(user, attribute_names=["roles"])
    for role in user.roles:
        await db.refresh(role, attribute_names=["permissions"])
    return user


# 便捷角色码常量
ADMIN = RoleCode.ADMIN.value
ENGINEER = RoleCode.ENGINEER.value
SUPERVISOR = RoleCode.SUPERVISOR.value
OPERATOR = RoleCode.OPERATOR.value
AUDITOR = RoleCode.AUDITOR.value
