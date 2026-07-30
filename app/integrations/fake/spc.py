"""SPC mock 客户端。"""

from __future__ import annotations

from datetime import datetime

from app.integrations.base import IntegrationClient
from app.integrations.dtos import SpcChartDTO, SpcEventDTO
from app.integrations.fake.store import FakeStore


class FakeSpcClient(IntegrationClient):
    system_code = "spc"

    def __init__(self, store: FakeStore):
        self.store = store

    async def fetch_ooc_events(self, since: datetime | None = None) -> list[SpcEventDTO]:
        if since is None:
            return list(self.store.spc_events)
        return [e for e in self.store.spc_events if e.detected_at > since]

    async def get_chart(self, chart_id: str) -> SpcChartDTO | None:
        return self.store.spc_charts.get(chart_id)

    async def record_event(self, event: SpcEventDTO) -> SpcEventDTO:
        self.store.spc_events.append(event)
        chart = self.store.spc_charts.get(event.chart_id)
        if chart:
            chart.last_ooc_at = event.detected_at
            chart.last_value = event.value
        return event
