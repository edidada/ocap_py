"""DMS（缺陷管理）mock 客户端。"""

from __future__ import annotations

from app.integrations.base import IntegrationClient
from app.integrations.dtos import DefectDTO
from app.integrations.fake.store import FakeStore


class FakeDmsClient(IntegrationClient):
    system_code = "dms"

    def __init__(self, store: FakeStore):
        self.store = store

    async def fetch_defects(self, batch_id: str | None = None) -> list[DefectDTO]:
        defects = list(self.store.defects.values())
        if batch_id:
            defects = [d for d in defects if d.batch_id == batch_id]
        return defects

    async def record_defect(self, item: DefectDTO) -> DefectDTO:
        self.store.defects[item.defect_id] = item
        return item
