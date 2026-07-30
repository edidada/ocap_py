"""MES mock 客户端：批次 Hold/Release/Scrap。"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.integrations.base import IntegrationClient
from app.integrations.dtos import BatchDTO, DispositionResultDTO
from app.integrations.fake.store import FakeStore


class FakeMesClient(IntegrationClient):
    system_code = "mes"

    def __init__(self, store: FakeStore):
        self.store = store

    async def get_batch(self, batch_id: str) -> BatchDTO:
        batch = self.store.batches.get(batch_id)
        if batch is None:
            raise NotFoundError(f"批次不存在: {batch_id}")
        return batch

    async def list_batches(self, status: str | None = None) -> list[BatchDTO]:
        batches = list(self.store.batches.values())
        if status:
            batches = [b for b in batches if b.status == status]
        return batches

    async def hold_batch(self, batch_id: str, reason: str = "") -> DispositionResultDTO:
        return await self._set_status(batch_id, "held", reason)

    async def release_batch(self, batch_id: str, reason: str = "") -> DispositionResultDTO:
        return await self._set_status(batch_id, "released", reason)

    async def scrap_batch(self, batch_id: str, reason: str = "") -> DispositionResultDTO:
        return await self._set_status(batch_id, "scrapped", reason)

    async def dispose_batch(self, batch_id: str, disposition: str, reason: str = "") -> DispositionResultDTO:
        """统一处置入口：disposition ∈ hold/release/scrap/rework。"""
        mapping = {
            "hold": self.hold_batch,
            "release": self.release_batch,
            "scrap": self.scrap_batch,
            "rework": lambda bid, r: self._set_status(bid, "rework", r),
        }
        handler = mapping.get(disposition)
        if handler is None:
            raise NotFoundError(f"不支持的处置类型: {disposition}")
        return await handler(batch_id, reason)

    async def _set_status(self, batch_id: str, new_status: str, reason: str) -> DispositionResultDTO:
        batch = await self.get_batch(batch_id)
        batch.status = new_status
        return DispositionResultDTO(
            success=True, batch_id=batch_id, new_status=new_status, message=reason
        )
