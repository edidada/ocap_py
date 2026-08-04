"""BP-G 分析域 service + API 测试。"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.domains.analytics import service
from app.domains.analytics.schemas import KpiSnapshotIn
from app.domains.common.enums import KpiCode, Period
from app.utils.time import utcnow


@pytest.mark.unit
class TestKpiService:
    async def test_record_and_list_kpis(self, db_session):
        now = utcnow()
        for i in range(5):
            await service.record_kpi(
                db_session, 1,
                KpiSnapshotIn(
                    kpi_code=KpiCode.MTTR,
                    period=Period.DAILY,
                    snapshot_at=now - timedelta(days=i),
                    value=60 + i * 10,
                    target=120,
                    count=10,
                ),
            )
        items = await service.list_kpis(db_session, 1, kpi_code=KpiCode.MTTR.value)
        assert len(items) == 5
        trend = await service.get_kpi_trend(db_session, 1, KpiCode.MTTR.value, days=30)
        assert len(trend.points) == 5


@pytest.mark.unit
class TestPareto:
    async def test_pareto_equipment(self, db_session):
        from app.domains.trigger.models import OcapEvent
        from app.domains.common.enums import EventSource, Severity, EventStatus

        now = utcnow()
        for i in range(10):
            eq = f"EQP-{i % 3 + 1:02d}"
            db_session.add(
                OcapEvent(
                    tenant_id=1, source=EventSource.SPC.value, severity=Severity.WARNING.value,
                    detected_at=now - timedelta(hours=i),
                    equipment_id=eq, title=f"事件 {i}",
                    status=EventStatus.OPEN.value,
                )
            )
        await db_session.flush()
        start = now - timedelta(days=2)
        result = await service.compute_pareto(db_session, 1, "equipment_id", start, now)
        assert result.total == 10
        assert len(result.items) == 3
        # 累计应约等于 1.0
        assert abs(result.items[-1].cumulative - 1.0) < 0.01


@pytest.mark.unit
class TestG2G:
    async def test_g2g_stats(self, db_session):
        now = utcnow()
        for i in range(5):
            d = now - timedelta(days=i)
            await service.record_g2g(
                db_session, 1, event_id=i + 1, detected_at=d,
                resolved_at=d + timedelta(minutes=30 + i * 10),
                breakdown={"rca": 10, "action": 20 + i * 10},
            )
        stats = await service.compute_g2g_stats(db_session, 1, days=30)
        assert stats.total_cycles == 5
        assert stats.avg_minutes > 0
        assert "rca" in stats.avg_breakdown


@pytest.mark.unit
class Test8DReport:
    async def test_generate_8d(self, db_session):
        # 创建一个 event + rca + action
        from app.domains.trigger.models import OcapEvent
        from app.domains.common.enums import EventSource, Severity, EventStatus
        from app.domains.rca.models import RcaRecord
        from app.domains.common.enums import RcaMethod, RcaStatus
        from app.domains.action.models import Action
        from app.domains.common.enums import ActionType, ActionStatus

        now = utcnow()
        ev = OcapEvent(
            tenant_id=1, source=EventSource.MANUAL.value, severity=Severity.CRITICAL.value,
            detected_at=now, title="严重漂移", status=EventStatus.RESOLVED.value,
        )
        db_session.add(ev)
        await db_session.flush()
        rca = RcaRecord(
            tenant_id=1, event_id=ev.id, method=RcaMethod.FIVE_WHY.value,
            status=RcaStatus.CONCLUDED.value,
            root_cause="传感器老化导致参数漂移",
            conclusion="更换传感器并重新校准",
        )
        db_session.add(rca)
        act = Action(
            tenant_id=1, event_id=ev.id, type=ActionType.MAINTENANCE.value,
            title="更换传感器", status=ActionStatus.COMPLETED.value,
            completed_at=now,
        )
        db_session.add(act)
        await db_session.flush()
        report = await service.generate_8d_report(db_session, 1, ev.id)
        assert "传感器老化" in report.d4_root_cause
        assert report.event_id == ev.id
        assert report.generated_at is not None


@pytest.mark.unit
class TestRam:
    async def test_compute_ram_no_samples(self, db_session):
        now = utcnow()
        ram = await service.compute_ram(
            db_session, 1, "EQP-01", now - timedelta(days=7), now
        )
        assert ram.availability > 0
        assert ram.reliability_mtbf_hours > 0


@pytest.mark.unit
class TestAnalyticsAPI:
    async def test_kpi_api(self, authed_client):
        now = utcnow()
        resp = await authed_client.post(
            "/api/v1/analytics/kpis",
            json={
                "kpi_code": "mttr",
                "period": "daily",
                "snapshot_at": now.isoformat(),
                "value": 85.5,
                "target": 120,
                "count": 10,
            },
        )
        assert resp.status_code == 201, resp.text
        listed = await authed_client.get("/api/v1/analytics/kpis?kpi_code=mttr")
        assert len(listed.json()) >= 1
        trend = await authed_client.get("/api/v1/analytics/kpis/trend?kpi_code=mttr&days=30")
        assert trend.status_code == 200

    async def test_pareto_api(self, authed_client):
        resp = await authed_client.get("/api/v1/analytics/pareto?dimension=equipment_id&days=30")
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_g2g_stats_api(self, authed_client):
        resp = await authed_client.get("/api/v1/analytics/g2g/stats")
        assert resp.status_code == 200
        assert "total_cycles" in resp.json()

    async def test_report_8d_api(self, authed_client):
        resp = await authed_client.get("/api/v1/analytics/reports/8d/99999")
        assert resp.status_code == 200
        assert "d1_team" in resp.json()
