"""触发域 API 测试。"""

from __future__ import annotations

import pytest

from app.domains.common.enums import EventSource, EventStatus, Severity


@pytest.mark.unit
class TestTriggerAPI:
    async def test_create_event(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/triggers/events",
            json={
                "source": "manual",
                "severity": "critical",
                "equipment_id": "EQP-01",
                "process_step": "etch",
                "title": "手动触发",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == EventStatus.OPEN.value
        assert data["severity"] == Severity.CRITICAL.value

    async def test_list_events(self, authed_client):
        await authed_client.post(
            "/api/v1/triggers/events",
            json={"source": "manual", "equipment_id": "EQP-01"},
        )
        resp = await authed_client.get("/api/v1/triggers/events")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    async def test_get_event(self, authed_client):
        create = await authed_client.post(
            "/api/v1/triggers/events", json={"source": "manual", "equipment_id": "EQP-02"}
        )
        eid = create.json()["id"]
        resp = await authed_client.get(f"/api/v1/triggers/events/{eid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == eid

    async def test_get_event_not_found(self, authed_client):
        resp = await authed_client.get("/api/v1/triggers/events/9999")
        assert resp.status_code == 404

    async def test_advance_event(self, authed_client):
        create = await authed_client.post(
            "/api/v1/triggers/events", json={"source": "manual"}
        )
        eid = create.json()["id"]
        resp = await authed_client.post(
            f"/api/v1/triggers/events/{eid}/advance", json={"status": "in_progress"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    async def test_advance_invalid_transition(self, authed_client):
        create = await authed_client.post(
            "/api/v1/triggers/events", json={"source": "manual"}
        )
        eid = create.json()["id"]
        resp = await authed_client.post(
            f"/api/v1/triggers/events/{eid}/advance", json={"status": "open"}
        )
        assert resp.status_code == 409

    async def test_ingest_event(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/triggers/events/ingest",
            json={
                "source": "spc",
                "severity": "critical",
                "equipment_id": "EQP-01",
                "parameters": {"value": 106.5},
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["created"] is True

    async def test_rule_crud(self, authed_client):
        create = await authed_client.post(
            "/api/v1/triggers/rules",
            json={
                "code": "api-rule-1",
                "name": "API 规则",
                "source": "spc",
                "condition": {"severity": ["critical"]},
                "priority": 5,
            },
        )
        assert create.status_code == 201, create.text
        rid = create.json()["id"]

        listed = await authed_client.get("/api/v1/triggers/rules")
        assert any(r["code"] == "api-rule-1" for r in listed.json())

        updated = await authed_client.patch(
            f"/api/v1/triggers/rules/{rid}", json={"priority": 99}
        )
        assert updated.status_code == 200
        assert updated.json()["priority"] == 99

        published = await authed_client.post(f"/api/v1/triggers/rules/{rid}/publish")
        assert published.status_code == 200
        assert published.json()["version"] == 1

    async def test_unauthorized(self, client):
        resp = await client.get("/api/v1/triggers/events")
        assert resp.status_code == 401
