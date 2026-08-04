"""BP-H 合规与审计域测试。"""

from __future__ import annotations

import pytest

from app.domains.common.enums import AuditAction, ConfigItemScope
from app.domains.compliance import service
from app.domains.compliance.schemas import (
    ConfigItemIn,
    RetentionPolicyIn,
    SpcSpecIn,
)
from app.utils.time import utcnow


@pytest.mark.unit
class TestAuditChain:
    async def test_audit_chain_intact(self, db_session):
        # 写 5 条审计
        for i in range(5):
            await service.write_audit(
                db_session, 1, user_id=100, action=AuditAction.CREATE,
                resource_type=f"Res{i}", resource_id=i, before={"v": i}, after={"v": i + 1},
            )
        broken = await service.verify_audit_chain(db_session, 1, limit=10)
        assert broken == []

    async def test_audit_chain_detects_tamper(self, db_session):
        for i in range(3):
            await service.write_audit(
                db_session, 1, user_id=100, action=AuditAction.UPDATE,
                resource_type="R", resource_id=1, before={}, after={},
            )
        await db_session.flush()
        # 篡改中间记录
        from app.domains.compliance.models import AuditLog
        from sqlalchemy import select
        logs = (await db_session.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
        logs[1].after = {"tampered": True}
        await db_session.flush()
        broken = await service.verify_audit_chain(db_session, 1, limit=10)
        assert len(broken) >= 1


@pytest.mark.unit
class TestRetentionPolicy:
    async def test_upsert_retention(self, db_session):
        p = await service.upsert_retention_policy(
            db_session, 1, RetentionPolicyIn(record_type="spc_data", retain_days=180, disposal_action="archive")
        )
        assert p.retain_days == 180
        # update 同一 record_type
        p2 = await service.upsert_retention_policy(
            db_session, 1, RetentionPolicyIn(record_type="spc_data", retain_days=365, disposal_action="archive")
        )
        assert p2.id == p.id
        assert p2.retain_days == 365
        items = await service.list_retention_policies(db_session, 1)
        assert len(items) == 1


@pytest.mark.unit
class TestSpcSpec:
    async def test_create_and_update_spec(self, db_session):
        spec = await service.create_spc_spec(
            db_session, 1,
            SpcSpecIn(chart_id="XBAR_A", parameter="Thickness", ucl=10, lcl=2, target=6, sample_size=5),
        )
        assert spec.version == 1
        # 更新
        spec2 = await service.update_spc_spec(
            db_session, 1, spec.id,
            SpcSpecIn(chart_id="XBAR_A", parameter="Thickness", ucl=11, lcl=1, target=6, sample_size=5),
            actor=9,
        )
        assert spec2.version == 2
        assert spec2.approved_by == 9
        assert spec2.approved_at is not None
        # 版本历史
        from app.domains.compliance.models import SpcSpecVersion
        from sqlalchemy import select
        vers = (await db_session.execute(select(SpcSpecVersion).where(SpcSpecVersion.spec_id == spec.id))).scalars().all()
        assert len(vers) == 2
        items = await service.list_spc_specs(db_session, 1, "XBAR_A")
        assert len(items) == 1


@pytest.mark.unit
class TestConfig:
    async def test_upsert_and_list(self, db_session):
        cfg = await service.upsert_config(
            db_session, 1,
            ConfigItemIn(scope=ConfigItemScope.TENANT, key="g2g.sla_minutes",
                         value={"sla": 1440}, description="G2G SLA"),
        )
        assert cfg.key == "g2g.sla_minutes"
        get = await service.get_config(db_session, 1, "tenant", "g2g.sla_minutes")
        assert get.value == {"sla": 1440}
        items = await service.list_configs(db_session, 1, scope="tenant")
        assert len(items) == 1


@pytest.mark.unit
class TestComplianceAPI:
    async def test_spc_spec_api(self, admin_client):
        """admin_client 拥有 iam:admin / iam:auditor / ocap:* / spc:spec:* 权限。"""
        resp = await admin_client.post(
            "/api/v1/compliance/spc-specs",
            json={"chart_id": "XBAR_B", "parameter": "CD", "ucl": 9, "lcl": 1, "target": 5, "sample_size": 4},
        )
        assert resp.status_code == 201, resp.text
        spec_id = resp.json()["id"]
        resp2 = await admin_client.put(
            f"/api/v1/compliance/spc-specs/{spec_id}",
            json={"chart_id": "XBAR_B", "parameter": "CD", "ucl": 10, "lcl": 0, "target": 5, "sample_size": 5},
        )
        assert resp2.status_code == 200
        assert resp2.json()["version"] == 2

    async def test_retention_api(self, admin_client):
        resp = await admin_client.post(
            "/api/v1/compliance/retention",
            json={"record_type": "spc_data", "retain_days": 365, "disposal_action": "archive"},
        )
        assert resp.status_code == 201
        listed = await admin_client.get("/api/v1/compliance/retention")
        assert listed.status_code == 200
        assert len(listed.json()) >= 1

    async def test_config_api(self, admin_client):
        resp = await admin_client.post(
            "/api/v1/compliance/configs",
            json={"scope": "tenant", "key": "sla.g2g", "value": {"minutes": 1440}},
        )
        assert resp.status_code == 201
        get = await admin_client.get("/api/v1/compliance/configs/tenant/sla.g2g")
        assert get.status_code == 200
        assert get.json()["value"]["minutes"] == 1440
