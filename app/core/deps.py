"""FastAPI 依赖注入：数据库会话、当前用户、角色/权限校验、租户上下文。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, PermissionDenied
from app.core.security import decode_token
from app.db.session import get_db
from app.domains.iam.models import User, load_user_with_relations

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 解析当前用户。支持测试通过 request.app.state 注入测试用户。"""
    test_user = getattr(request.app.state, "test_user", None)
    if test_user is not None:
        return test_user

    if not token:
        raise AuthError("缺少认证令牌")
    payload = decode_token(token, expected_type="access")
    user_id = int(payload["sub"])
    user = await load_user_with_relations(db, user_id)
    if user is None or not user.is_active:
        raise AuthError("用户不存在或已禁用")
    # 写入租户上下文供后续依赖使用
    request.state.tenant_id = user.tenant_id
    return user


def require_role(*roles: str) -> Callable[..., Awaitable[User]]:
    """要求当前用户具有指定角色之一（admin 视为通配）。"""

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if "admin" in user.role_codes or (set(roles) & user.role_codes):
            return user
        raise PermissionDenied(f"需要角色之一: {', '.join(roles)}")

    return _dep


def require_permission(*perms: str) -> Callable[..., Awaitable[User]]:
    """要求当前用户具有指定权限之一（admin 视为通配）。"""

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if "admin" in user.role_codes or (set(perms) & user.permission_codes):
            return user
        raise PermissionDenied(f"需要权限之一: {', '.join(perms)}")

    return _dep


async def get_tenant_id(user: User = Depends(get_current_user)) -> int:
    """从当前用户获取租户 ID。"""
    return user.tenant_id
