"""集成注册表：按 system_code 获取客户端，mock 模式共享 FakeStore。"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.integrations.base import IntegrationClient
from app.integrations.fake.apc import FakeApcClient
from app.integrations.fake.ams import FakeAmsClient
from app.integrations.fake.dms import FakeDmsClient
from app.integrations.fake.fdc import FakeFdcClient
from app.integrations.fake.mes import FakeMesClient
from app.integrations.fake.recipe import FakeRecipeClient
from app.integrations.fake.spc import FakeSpcClient
from app.integrations.fake.sfmm import FakeSfmmClient
from app.integrations.fake.store import FakeStore
from app.integrations.fake.yms import FakeYmsClient

_FAKE_FACTORIES: dict[str, type] = {
    "spc": FakeSpcClient,
    "fdc": FakeFdcClient,
    "mes": FakeMesClient,
    "ams": FakeAmsClient,
    "sfmm": FakeSfmmClient,
    "yms": FakeYmsClient,
    "dms": FakeDmsClient,
    "apc": FakeApcClient,
    "recipe": FakeRecipeClient,
}


class IntegrationRegistry:
    """集成客户端注册表。默认全部走 mock。"""

    def __init__(self, store: FakeStore | None = None):
        self.store = store or FakeStore.empty()
        self._clients: dict[str, IntegrationClient] = {}

    @classmethod
    def with_fakes(cls, store: FakeStore | None = None) -> "IntegrationRegistry":
        """构造全部 mock 的注册表。"""
        return cls(store=store)

    @classmethod
    def from_seed(cls, seed_dir: str | Path | None = None) -> "IntegrationRegistry":
        """从 seed 数据构造 mock 注册表。"""
        if seed_dir is None:
            seed_dir = settings.SEED_DATA_DIR
        store = FakeStore.from_seed(Path(seed_dir) / "10_fake_store.yaml")
        return cls(store=store)

    def get(self, system_code: str) -> IntegrationClient:
        """获取指定系统的客户端。"""
        if system_code not in _FAKE_FACTORIES:
            raise NotFoundError(f"不支持的集成系统: {system_code}")
        if system_code not in self._clients:
            factory = _FAKE_FACTORIES[system_code]
            self._clients[system_code] = factory(self.store)
        return self._clients[system_code]

    def supported_systems(self) -> list[str]:
        return list(_FAKE_FACTORIES)


# 默认依赖（生产用 from_seed；测试通过 dependency_overrides 替换）
def get_integration_registry() -> IntegrationRegistry:
    """FastAPI 依赖：返回集成注册表。"""
    return IntegrationRegistry.from_seed()
