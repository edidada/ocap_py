"""YMS（良率管理）mock 客户端。"""

from __future__ import annotations

from app.integrations.base import IntegrationClient
from app.integrations.dtos import YieldDTO
from app.integrations.fake.store import FakeStore


class FakeYmsClient(IntegrationClient):
    system_code = "yms"

    def __init__(self, store: FakeStore):
        self.store = store

    async def fetch_yields(self, batch_id: str | None = None) -> list[YieldDTO]:
        yields = list(self.store.yields.values())
        if batch_id:
            yields = [y for y in yields if y.batch_id == batch_id]
        return yields

    async def record_yield(self, item: YieldDTO) -> YieldDTO:
        self.store.yields[item.batch_id] = item
        return item
