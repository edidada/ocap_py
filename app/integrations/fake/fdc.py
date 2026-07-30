"""FDC mock 客户端。"""

from __future__ import annotations

from app.integrations.base import IntegrationClient
from app.integrations.dtos import FdcAlarmDTO
from app.integrations.fake.store import FakeStore


class FakeFdcClient(IntegrationClient):
    system_code = "fdc"

    def __init__(self, store: FakeStore):
        self.store = store

    async def fetch_alarms(self, equipment_id: str | None = None) -> list[FdcAlarmDTO]:
        alarms = list(self.store.fdc_alarms.values())
        if equipment_id:
            alarms = [a for a in alarms if a.equipment_id == equipment_id]
        return alarms

    async def get_alarm(self, alarm_id: str) -> FdcAlarmDTO | None:
        return self.store.fdc_alarms.get(alarm_id)

    async def raise_alarm(self, alarm: FdcAlarmDTO) -> FdcAlarmDTO:
        self.store.fdc_alarms[alarm.alarm_id] = alarm
        return alarm
