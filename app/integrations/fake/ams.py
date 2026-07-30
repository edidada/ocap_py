"""AMS（报警管理）mock 客户端。"""

from __future__ import annotations

from app.integrations.base import IntegrationClient
from app.integrations.dtos import AlarmDTO
from app.integrations.fake.store import FakeStore


class FakeAmsClient(IntegrationClient):
    system_code = "ams"

    def __init__(self, store: FakeStore):
        self.store = store

    async def fetch_alarms(self, equipment_id: str | None = None) -> list[AlarmDTO]:
        alarms = [a for a in self.store.ams_alarms.values() if a.cleared_at is None]
        if equipment_id:
            alarms = [a for a in alarms if a.equipment_id == equipment_id]
        return alarms

    async def clear_alarm(self, alarm_id: str) -> bool:
        alarm = self.store.ams_alarms.get(alarm_id)
        if alarm is None:
            return False
        from datetime import datetime, timezone

        alarm.cleared_at = datetime.now(timezone.utc)
        return True
