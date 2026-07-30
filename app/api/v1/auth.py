"""认证 API：登录、刷新、当前用户。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.iam.schemas import (
    LoginRequest,
    MeOut,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.domains.iam.service import (
    authenticate,
    issue_tokens,
    refresh_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """用户名/密码登录，签发 JWT。"""
    user = await authenticate(
        db, username=payload.username, password=payload.password, tenant_code=payload.tenant_code
    )
    return issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """刷新访问令牌。"""
    return await refresh_access_token(db, payload.refresh_token)


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    """获取当前用户信息。"""
    return MeOut(
        user=UserOut(
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
    )
