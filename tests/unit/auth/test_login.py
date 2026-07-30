"""认证 API 与安全模块测试。"""

from __future__ import annotations

import pytest

from app.core.security import (
    Sha256Hasher,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import AuthError


@pytest.mark.unit
class TestPasswordHashing:
    def test_hash_and_verify(self):
        h = hash_password("secret")
        assert h != "secret"
        assert verify_password("secret", h) is True
        assert verify_password("wrong", h) is False

    def test_sha256_hasher_deterministic(self):
        h1 = Sha256Hasher().hash("abc")
        h2 = Sha256Hasher().hash("abc")
        assert h1 == h2


@pytest.mark.unit
class TestJwt:
    def test_access_token_roundtrip(self):
        token = create_access_token(sub="42", tenant_id=1, roles=["engineer"], scopes=["ocap:event:read"])
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == "42"
        assert payload["tenant_id"] == 1
        assert payload["roles"] == ["engineer"]
        assert payload["type"] == "access"

    def test_decode_invalid_token_raises(self):
        with pytest.raises(AuthError):
            decode_token("not-a-jwt")

    def test_token_type_mismatch_raises(self):
        refresh = create_refresh_token(sub="42", tenant_id=1)
        with pytest.raises(AuthError):
            decode_token(refresh, expected_type="access")


@pytest.mark.unit
class TestAuthAPI:
    async def test_login_success(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "engineer", "password": "pass", "tenant_code": "fab01"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["user"]["username"] == "engineer"
        assert "ocap:event:read" in data["user"]["permissions"]

    async def test_login_wrong_password(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "engineer", "password": "bad", "tenant_code": "fab01"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_user(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "pass", "tenant_code": "fab01"},
        )
        assert resp.status_code == 401

    async def test_login_wrong_tenant(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "engineer", "password": "pass", "tenant_code": "nope"},
        )
        assert resp.status_code == 401

    async def test_me_with_token(self, authed_client):
        resp = await authed_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()["user"]
        assert data["username"] == "engineer"
        assert any(r["code"] == "engineer" for r in data["roles"])

    async def test_me_without_token(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_refresh_token(self, client):
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "engineer", "password": "pass", "tenant_code": "fab01"},
        )
        refresh_token = login.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    async def test_refresh_with_access_token_fails(self, client):
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "engineer", "password": "pass", "tenant_code": "fab01"},
        )
        access = login.json()["access_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401
