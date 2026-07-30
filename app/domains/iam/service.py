"""IAM 域服务：认证、令牌签发。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.domains.iam.models import Tenant, User, load_user_with_relations
from app.domains.iam.schemas import TokenResponse, UserOut


async def authenticate(
    db: AsyncSession, *, username: str, password: str, tenant_code: str | None
) -> User:
    """用户名/密码认证。tenant_code 为空时取首个匹配用户（单租户便利）。"""
    if tenant_code:
        tenant_stmt = select(Tenant).where(Tenant.code == tenant_code)
        tenant = (await db.execute(tenant_stmt)).scalar_one_or_none()
        if tenant is None:
            raise AuthError("租户不存在")
        stmt = select(User).where(User.tenant_id == tenant.id, User.username == username)
    else:
        stmt = select(User).where(User.username == username)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("用户名或密码错误")
    await db.refresh(user, attribute_names=["roles"])
    for role in user.roles:
        await db.refresh(role, attribute_names=["permissions"])
    if not verify_password(password, user.password_hash):
        raise AuthError("用户名或密码错误")
    return user


def issue_tokens(user: User) -> TokenResponse:
    """为用户签发访问/刷新令牌。"""
    roles = list(user.role_codes)
    scopes = list(user.permission_codes)
    access = create_access_token(
        sub=str(user.id), tenant_id=user.tenant_id, roles=roles, scopes=scopes
    )
    refresh = create_refresh_token(sub=str(user.id), tenant_id=user.tenant_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_to_user_out(user),
    )


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """校验刷新令牌并签发新的访问令牌。"""
    payload = decode_token(refresh_token, expected_type="refresh")
    user = await load_user_with_relations(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("用户不存在或已禁用")
    access = create_access_token(
        sub=str(user.id),
        tenant_id=user.tenant_id,
        roles=list(user.role_codes),
        scopes=list(user.permission_codes),
    )
    new_refresh = create_refresh_token(sub=str(user.id), tenant_id=user.tenant_id)
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_to_user_out(user),
    )


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        roles=[
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "permissions": [
                    {"id": p.id, "code": p.code, "description": p.description}
                    for p in r.permissions
                ],
            }
            for r in user.roles
        ],
        permissions=list(user.permission_codes),
    )
