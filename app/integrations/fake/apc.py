"""APC（先进过程控制）mock 客户端。"""

from __future__ import annotations

from app.integrations.base import IntegrationClient
from app.integrations.fake.store import FakeStore


class FakeApcClient(IntegrationClient):
    system_code = "apc"

    def __init__(self, store: FakeStore):
        self.store = store
        # 模型调节状态：equipment_id -> {in_range: bool}
        self._model_status: dict[str, bool] = {}

    async def get_model_status(self, equipment_id: str) -> dict:
        return {"equipment_id": equipment_id, "in_range": self._model_status.get(equipment_id, True)}

    async def set_model_out_of_range(self, equipment_id: str) -> dict:
        self._model_status[equipment_id] = False
        return await self.get_model_status(equipment_id)
