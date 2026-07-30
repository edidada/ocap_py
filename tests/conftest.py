"""pytest 全局夹具。

SQLite 内存库 + StaticPool（单连接共享）+ 模型自动发现 + seed + JWT。
所有 domain 的 models.py 会被自动发现并导入，以填充 Base.metadata。
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import Sha256Hasher, set_password_hasher
from app.db.base import Base
from app.db.seed.loader import SeedLoader
from app.db.session import get_db
from app.main import app

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _import_all_models() -> None:
    """递归导入 app/domains 下所有 models.py，填充 Base.metadata。"""
    domains_dir = _PROJECT_ROOT / "app" / "domains"
    for path in sorted(domains_dir.rglob("models.py")):
        rel = path.relative_to(_PROJECT_ROOT).with_suffix("")
        module_name = ".".join(rel.parts)
        importlib.import_module(module_name)


@pytest.fixture(autouse=True)
def fast_password_hasher() -> AsyncIterator[None]:
    """单测用快速 sha256 哈希，避免 bcrypt 慢；生产仍用 bcrypt。"""
    from app.core import security

    saved = security._hasher
    set_password_hasher(Sha256Hasher())
    try:
        yield
    finally:
        security._hasher = saved


@pytest_asyncio.fixture
async def engine():
    """每测独立的 SQLite 内存引擎（StaticPool 单连接共享）。"""
    _import_all_models()
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(eng.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncIterator[AsyncSession]:
    """供 service 级单测直接使用的会话。"""
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def seeded_db(session_factory) -> AsyncSession:
    """加载 seed 并返回会话（seed 已提交，对其他会话可见）。"""
    async with session_factory() as s:
        loader = SeedLoader(s, str(_PROJECT_ROOT / "app" / "db" / "seed" / "data"))
        await loader.load()
        await s.commit()
        return s


def _make_get_db_override(session_factory: async_sessionmaker[AsyncSession]):
    async def _override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    return _override


@pytest.fixture
def fake_store():
    """从 seed 装载的 FakeStore。"""
    from app.integrations.fake.store import FakeStore

    return FakeStore.from_seed(_PROJECT_ROOT / "app" / "db" / "seed" / "data" / "10_fake_store.yaml")


@pytest.fixture
def fake_integrations(fake_store):
    """全部 mock 的集成注册表。"""
    from app.integrations.registry import IntegrationRegistry

    return IntegrationRegistry.with_fakes(fake_store)


@pytest_asyncio.fixture
async def app_overrides(seeded_db, session_factory, fake_integrations):
    """覆盖 get_db 与集成注册表，使用测试会话工厂与 mock 客户端。"""
    from app.integrations.registry import get_integration_registry

    override = _make_get_db_override(session_factory)
    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_integration_registry] = lambda: fake_integrations
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app_overrides) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_overrides)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def authed_client(client) -> AsyncClient:
    """以 engineer 身份登录的客户端。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "engineer", "password": "pass", "tenant_code": "fab01"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def admin_client(client) -> AsyncClient:
    """以 admin 身份登录的客户端。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "pass", "tenant_code": "fab01"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
