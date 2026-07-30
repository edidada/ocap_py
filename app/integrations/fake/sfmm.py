"""SFMM（设备维护管理）mock 客户端。"""

from __future__ import annotations

from datetime import datetime, timezone

from app.integrations.base import IntegrationClient
from app.integrations.dtos import MaintenanceOrderDTO
from app.integrations.fake.store import FakeStore


class FakeSfmmClient(IntegrationClient):
    system_code = "sfmm"

    def __init__(self, store: FakeStore):
        self.store = store

    async def create_maintenance_order(
        self, equipment_id: str, order_type: str = "corrective"
    ) -> MaintenanceOrderDTO:
        order_id = f"MO-{len(self.store.maintenance_orders) + 1:04d}"
        order = MaintenanceOrderDTO(
            order_id=order_id,
            equipment_id=equipment_id,
            type=order_type,
            status="open",
            created_at=datetime.now(timezone.utc),
        )
        self.store.maintenance_orders[order_id] = order
        return order

    async def get_order(self, order_id: str) -> MaintenanceOrderDTO | None:
        return self.store.maintenance_orders.get(order_id)

    async def complete_order(self, order_id: str) -> MaintenanceOrderDTO | None:
        order = self.store.maintenance_orders.get(order_id)
        if order:
            order.status = "done"
        return order
