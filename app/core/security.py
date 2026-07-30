"""JWT 签发/校验与密码哈希。

密码哈希可注入：生产用 bcrypt，单测用 Sha256Hasher（快、确定）。
JWT 使用 HS256，claims 含 sub/tenant_id/roles/scopes/exp/iat/jti。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import AuthError


# ----------------------------- 密码哈希 -----------------------------


class PasswordHasher(Protocol):
    def hash(self, plain: str) -> str: ...
    def verify(self, plain: str, hashed: str) -> bool: ...


class BcryptHasher:
    """生产用 bcrypt 哈希。"""

    def hash(self, plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False


class Sha256Hasher:
    """单测用快速哈希（带盐）。不要在生产使用。"""

    _SALT = "ocap-test-salt"

    def hash(self, plain: str) -> str:
        return hashlib.sha256(f"{self._SALT}:{plain}".encode("utf-8")).hexdigest()

    def verify(self, plain: str, hashed: str) -> bool:
        return hmac.compare_digest(self.hash(plain), hashed)


# 可替换的哈希器（单测通过 set_password_hasher 替换）
_hasher: PasswordHasher = BcryptHasher()


def set_password_hasher(hasher: PasswordHasher) -> None:
    """替换全局密码哈希器（测试用）。"""
    global _hasher
    _hasher = hasher


def get_password_hasher() -> PasswordHasher:
    return _hasher


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)


# ----------------------------- JWT -----------------------------


@dataclass
class TokenClaims:
    sub: str
    tenant_id: int
    roles: list[str]
    scopes: list[str]
    exp: datetime
    iat: datetime
    jti: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    *, sub: str, tenant_id: int, roles: list[str], scopes: list[str] | None = None
) -> str:
    now = _now()
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "roles": roles,
        "scopes": scopes or [],
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(*, sub: str, tenant_id: int) -> str:
    now = _now()
    exp = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str | None = None) -> dict:
    """解码并校验 JWT。失败抛 AuthError。"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError(f"无效令牌: {exc}") from exc
    if expected_type and payload.get("type") != expected_type:
        raise AuthError("令牌类型不符")
    return payload
