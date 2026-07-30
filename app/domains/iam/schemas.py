"""IAM 域 Schema。"""

from __future__ import annotations

from app.domains.common.mixins import ORMBase, TimestampOut


class PermissionOut(ORMBase):
    id: int
    code: str
    description: str


class RoleOut(ORMBase):
    id: int
    code: str
    name: str
    permissions: list[PermissionOut] = []


class UserOut(ORMBase):
    id: int
    tenant_id: int
    username: str
    email: str
    is_active: bool
    roles: list[RoleOut] = []
    permissions: list[str] = []


class LoginRequest(ORMBase):
    username: str
    password: str
    tenant_code: str | None = None


class RefreshRequest(ORMBase):
    refresh_token: str


class TokenResponse(ORMBase):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class MeOut(ORMBase):
    user: UserOut
