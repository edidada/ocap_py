"""BP-C 根因分析域 service + API 测试。"""

from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.common.enums import RcaMethod, RcaStatus
from app.domains.rca import service
from app.domains.rca.schemas import (
    CpmRequest,
    DataCorrelationEntry,
    FishboneEntry,
    FiveWhyEntry,
    RcaCreate,
    RcaUpdate,
)


@pytest.mark.unit
class TestRcaService:
    async def test_create_and_get_rca(self, db_session):
        rca = await service.create_rca(db_session, 1, RcaCreate(event_id=1), user_id=2)
        assert rca.id is not None
        assert rca.status == RcaStatus.IN_PROGRESS.value
        got = await service.get_rca(db_session, 1, rca.id)
        assert got.event_id == 1

    async def test_get_rca_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            await service.get_rca(db_session, 1, 9999)

    async def test_update_rca_conclude(self, db_session):
        rca = await service.create_rca(db_session, 1, RcaCreate(event_id=1), user_id=2)
        updated = await service.update_rca(
            db_session, 1, rca.id,
            RcaUpdate(root_cause="参数漂移", conclusion="调整 Recipe", status=RcaStatus.CONCLUDED),
        )
        assert updated.status == RcaStatus.CONCLUDED.value
        assert updated.concluded_at is not None
        assert updated.root_cause == "参数漂移"

    async def test_five_why_crud(self, db_session):
        rca = await service.create_rca(db_session, 1, RcaCreate(event_id=1), user_id=2)
        await service.add_five_why(db_session, 1, rca.id, FiveWhyEntry(level=1, question="为何漂移?", answer="传感器偏差"))
        await service.add_five_why(db_session, 1, rca.id, FiveWhyEntry(level=2, question="为何偏差?", answer="老化"))
        items = await service.list_five_why(db_session, 1, rca.id)
        assert len(items) == 2
        assert items[0].level == 1

    async def test_five_why_duplicate_level(self, db_session):
        rca = await service.create_rca(db_session, 1, RcaCreate(event_id=1), user_id=2)
        await service.add_five_why(db_session, 1, rca.id, FiveWhyEntry(level=1, question="Q"))
        with pytest.raises(ConflictError):
            await service.add_five_why(db_session, 1, rca.id, FiveWhyEntry(level=1, question="Q2"))

    async def test_fishbone_crud(self, db_session):
        rca = await service.create_rca(db_session, 1, RcaCreate(event_id=1), user_id=2)
        await service.add_fishbone(db_session, 1, rca.id, FishboneEntry(category="machine", cause="传感器老化"))
        await service.add_fishbone(db_session, 1, rca.id, FishboneEntry(category="method", cause="SOP 缺失"))
        items = await service.list_fishbone(db_session, 1, rca.id)
        assert len(items) == 2

    async def test_data_correlation(self, db_session):
        rca = await service.create_rca(db_session, 1, RcaCreate(event_id=1), user_id=2)
        await service.add_correlation(
            db_session, 1, rca.id,
            DataCorrelationEntry(source="spc", parameter="thickness", correlation="正相关", evidence={"r": 0.85}),
        )
        items = await service.list_correlations(db_session, 1, rca.id)
        assert len(items) == 1
        assert items[0].source == "spc"


@pytest.mark.unit
class TestCpm:
    async def test_cpm_match_high_score(self, db_session):
        candidates = [
            {"case_id": 1, "equipment_id": "EQP-01", "process_step": "etch", "anomaly_type": "drift"},
            {"case_id": 2, "equipment_id": "EQP-02", "process_step": "litho", "anomaly_type": "shift"},
        ]
        run = await service.run_cpm(
            db_session, 1,
            CpmRequest(event_id=1, context={"equipment_id": "EQP-01", "process_step": "etch", "anomaly_type": "drift"}),
            candidates=candidates,
        )
        assert run.top_score == 100
        assert run.matched_cases[0]["case_id"] == 1

    async def test_cpm_partial_match(self, db_session):
        candidates = [{"case_id": 1, "equipment_id": "EQP-01", "process_step": "etch"}]
        run = await service.run_cpm(
            db_session, 1,
            CpmRequest(event_id=1, context={"equipment_id": "EQP-01", "process_step": "litho"}),
            candidates=candidates,
        )
        # equipment 匹配(40) / (40+25) = 61%
        assert 50 <= run.top_score <= 70

    async def test_cpm_no_match(self, db_session):
        run = await service.run_cpm(
            db_session, 1,
            CpmRequest(event_id=1, context={"equipment_id": "EQP-99"}),
            candidates=[{"case_id": 1, "equipment_id": "EQP-01"}],
        )
        assert run.top_score == 0
        assert run.matched_cases == []


@pytest.mark.unit
class TestRepeatDetection:
    async def test_first_occurrence(self, db_session):
        from app.utils.time import utcnow

        result = await service.detect_repeat(db_session, 1, 1, "EQP-01|etch|drift", utcnow())
        assert result.repeat_count == 1
        assert result.is_systemic is False

    async def test_systemic_after_threshold(self, db_session):
        from app.utils.time import utcnow

        now = utcnow()
        for i in range(3):
            result = await service.detect_repeat(db_session, 1, i + 1, "EQP-01|etch|drift", now)
        assert result.repeat_count == 3
        assert result.is_systemic is True

    async def test_fingerprint(self):
        fp = service.compute_fingerprint("EQP-01", "etch", "drift")
        assert fp == "EQP-01|etch|drift"
        fp2 = service.compute_fingerprint(None, None, None)
        assert fp2 == "*|*|*"


@pytest.mark.unit
class TestRcaAPI:
    async def test_rca_lifecycle_via_api(self, authed_client):
        create = await authed_client.post("/api/v1/rcas", json={"event_id": 1, "method": "cpm"})
        assert create.status_code == 201, create.text
        rid = create.json()["id"]

        # 5-Why
        fw = await authed_client.post(
            f"/api/v1/rcas/{rid}/five-why", json={"level": 1, "question": "为何?", "answer": "因为"}
        )
        assert fw.status_code == 201
        fw_list = await authed_client.get(f"/api/v1/rcas/{rid}/five-why")
        assert len(fw_list.json()) == 1

        # 鱼骨图
        fb = await authed_client.post(
            f"/api/v1/rcas/{rid}/fishbone", json={"category": "machine", "cause": "老化"}
        )
        assert fb.status_code == 201

        # 更新结论
        upd = await authed_client.patch(
            f"/api/v1/rcas/{rid}",
            json={"root_cause": "漂移", "conclusion": "调整", "status": "concluded"},
        )
        assert upd.status_code == 200
        assert upd.json()["status"] == "concluded"

    async def test_cpm_via_api(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/rcas/cpm",
            json={"event_id": 1, "context": {"equipment_id": "EQP-01"}},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["top_score"] == 0  # 无候选
