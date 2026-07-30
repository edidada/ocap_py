"""BP-E 数据集成域 service + API 测试。"""

from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.common.enums import IntegrationMode, IntegrationSystem
from app.domains.integration import service
from app.domains.integration.schemas import (
    EventStreamIngest,
    IntegrationConfigCreate,
    IntegrationConfigUpdate,
)


@pytest.mark.unit
class TestIntegrationConfig:
    async def test_create_and_list_config(self, db_session):
        cfg = await service.create_config(
            db_session, 1,
            IntegrationConfigCreate(system=IntegrationSystem.SPC, mode=IntegrationMode.MOCK, endpoint="http://x"),
        )
        assert cfg.system == "spc"
        cfgs = await service.list_configs(db_session, 1)
        assert len(cfgs) == 1

    async def test_duplicate_config_conflict(self, db_session):
        await service.create_config(
            db_session, 1, IntegrationConfigCreate(system=IntegrationSystem.MES)
        )
        with pytest.raises(ConflictError):
            await service.create_config(
                db_session, 1, IntegrationConfigCreate(system=IntegrationSystem.MES)
            )

    async def test_update_config(self, db_session):
        cfg = await service.create_config(
            db_session, 1, IntegrationConfigCreate(system=IntegrationSystem.FDC)
        )
        updated = await service.update_config(
            db_session, 1, cfg.id, IntegrationConfigUpdate(enabled=False, endpoint="http://new")
        )
        assert updated.enabled is False
        assert updated.endpoint == "http://new"

    async def test_get_config_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            await service.get_config(db_session, 1, 9999)


@pytest.mark.unit
class TestSync:
    async def test_trigger_sync_success(self, db_session, fake_integrations):
        result = await service.trigger_sync(db_session, 1, "spc", fake_integrations)
        assert result.status == "done"
        assert result.records_count >= 0
        logs = await service.list_sync_logs(db_session, 1)
        assert logs.total == 1

    async def test_trigger_sync_failed(self, db_session):
        # 无 registry，模拟失败
        result = await service.trigger_sync(db_session, 1, "unknown", None)
        assert result.status == "done"  # 无 client 不报错，records=0
        assert result.records_count == 0


@pytest.mark.unit
class TestHealthCheck:
    async def test_health_check_all(self, fake_integrations):
        results = await service.health_check_all(fake_integrations)
        assert len(results) == 9  # 9 个系统
        assert all(r.status == "up" for r in results)


@pytest.mark.unit
class TestDataQuality:
    async def test_record_and_list_issues(self, db_session):
        await service.record_quality_issue(
            db_session, 1, "spc", "completeness", 0.85, {"missing": 3}
        )
        issues = await service.list_quality_issues(db_session, 1)
        assert len(issues) == 1
        assert issues[0].score == 0.85
        unresolved = await service.list_quality_issues(db_session, 1, resolved=False)
        assert len(unresolved) == 1


@pytest.mark.unit
class TestEventStream:
    async def test_ingest_event_stream(self, db_session):
        stream = await service.ingest_event_stream(
            db_session, 1,
            EventStreamIngest(source=IntegrationSystem.FDC, event_type="alarm", payload={"id": "a1"}),
        )
        assert stream.processed is False
        page = await service.list_event_streams(db_session, 1)
        assert page.total == 1


@pytest.mark.unit
class TestIntegrationAPI:
    async def test_config_crud_via_api(self, admin_client):
        create = await admin_client.post(
            "/api/v1/integrations/configs",
            json={"system": "spc", "mode": "mock", "endpoint": "http://spc"},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        listed = await admin_client.get("/api/v1/integrations/configs")
        assert any(c["system"] == "spc" for c in listed.json())
        upd = await admin_client.patch(
            f"/api/v1/integrations/configs/{cid}", json={"enabled": False}
        )
        assert upd.json()["enabled"] is False

    async def test_health_via_api(self, authed_client):
        resp = await authed_client.get("/api/v1/integrations/health")
        assert resp.status_code == 200
        assert len(resp.json()) == 9

    async def test_sync_via_api(self, authed_client):
        resp = await authed_client.post("/api/v1/integrations/sync/mes")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] in ("done", "failed")

    async def test_event_stream_via_api(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/integrations/event-streams",
            json={"source": "fdc", "event_type": "alarm", "payload": {"x": 1}},
        )
        assert resp.status_code == 201
        assert resp.json()["processed"] is False
