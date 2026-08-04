"""BP-I 平台域 service + API 测试。"""

from __future__ import annotations

import pytest

from app.core.pagination import PageParams
from app.domains.platform import service as svc
from app.domains.platform.schemas import ExportTaskCreate


@pytest.mark.unit
class TestNotifications:
    async def test_create_and_list(self, db_session):
        n = await svc.create_notification(
            db_session, 1, user_id=10, channel="im", template="event",
            title="新异常事件", body="EQP-01 有新事件",
        )
        await svc.mark_notification_sent(db_session, n.id)
        await db_session.flush()
        page = await svc.list_notifications(db_session, 1, 10, PageParams(page=1, size=20))
        assert page.total == 1
        assert page.items[0].status == "sent"


@pytest.mark.unit
class TestExports:
    def setup_method(self):
        svc.reset_export_db()

    async def test_create_and_list(self, db_session):
        task = await svc.create_export(
            db_session, 1, 100, ExportTaskCreate(resource="events", format="csv", parameters={"days": 30})
        )
        assert task.status == "completed"
        assert task.file_path is not None
        listed = await svc.list_exports(1)
        assert len(listed) == 1


@pytest.mark.unit
class TestPlatformAPI:
    async def test_notification_api(self, admin_client):
        resp = await admin_client.post(
            "/api/v1/platform/notifications?title=告警&body=测试&channel=im&template=generic"
        )
        assert resp.status_code == 201, resp.text
        listed = await admin_client.get("/api/v1/platform/notifications")
        assert listed.status_code == 200

    async def test_export_api(self, admin_client):
        resp = await admin_client.post(
            "/api/v1/platform/exports",
            json={"resource": "events", "format": "csv"},
        )
        assert resp.status_code == 201, resp.text
        listed = await admin_client.get("/api/v1/platform/exports")
        assert listed.status_code == 200
        assert len(listed.json()) >= 1
