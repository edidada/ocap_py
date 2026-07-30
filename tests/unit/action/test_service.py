"""BP-D 处置执行域 service + API 测试。"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.action import service
from app.domains.action.schemas import (
    ActionCreate,
    ActionUpdate,
    BatchDispositionRequest,
    ClosureRequest,
    SignRequest,
    SlaCreate,
)
from app.domains.common.enums import ActionStatus, ActionType, BatchDisposition
from app.utils.time import utcnow


@pytest.mark.unit
class TestActionService:
    async def test_create_and_get_action(self, db_session):
        action = await service.create_action(
            db_session, 1,
            ActionCreate(event_id=1, type=ActionType.HOLD, title="Hold 批次", description="厚度漂移"),
        )
        assert action.id is not None
        assert action.status == ActionStatus.PENDING.value
        got = await service.get_action(db_session, 1, action.id)
        assert got.title == "Hold 批次"

    async def test_list_actions_filter(self, db_session):
        await service.create_action(db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD))
        await service.create_action(db_session, 1, ActionCreate(event_id=2, type=ActionType.RECIPE_CHANGE))
        page = await service.list_actions(db_session, 1, event_id=1)
        assert page.total == 1

    async def test_execute_action(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.MAINTENANCE)
        )
        execution = await service.execute_action(db_session, 1, action.id, actor_id=2, detail="已修复")
        assert execution.status == ActionStatus.COMPLETED.value
        action2 = await service.get_action(db_session, 1, action.id)
        assert action2.status == ActionStatus.COMPLETED.value
        assert action2.completed_at is not None

    async def test_execute_terminal_action_conflict(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        await service.execute_action(db_session, 1, action.id, actor_id=2)
        with pytest.raises(ConflictError):
            await service.execute_action(db_session, 1, action.id, actor_id=2)

    async def test_rollback_action(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        await service.execute_action(db_session, 1, action.id, actor_id=2)
        rolled = await service.rollback_action(db_session, 1, action.id, actor_id=3, reason="误判")
        assert rolled.status == ActionStatus.ROLLED_BACK.value
        assert rolled.rolled_back_at is not None

    async def test_rollback_non_completed_conflict(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        with pytest.raises(ConflictError):
            await service.rollback_action(db_session, 1, action.id, actor_id=2)


@pytest.mark.unit
class TestElectronicSignature:
    async def test_sign_and_chain(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        s1 = await service.sign_action(db_session, 1, action.id, 2, SignRequest(meaning="approve"))
        s2 = await service.sign_action(db_session, 1, action.id, 3, SignRequest(meaning="verify"))
        assert s1.prev_hash == ""
        assert s2.prev_hash == s1.signature_hash
        assert s1.signature_hash != s2.signature_hash

    async def test_verify_chain_valid(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        await service.sign_action(db_session, 1, action.id, 2, SignRequest())
        await service.sign_action(db_session, 1, action.id, 3, SignRequest())
        sigs = await service.list_signatures(db_session, 1, action.id)
        assert service.verify_signature_chain(sigs) is True

    async def test_verify_chain_tampered(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        await service.sign_action(db_session, 1, action.id, 2, SignRequest())
        sigs = await service.list_signatures(db_session, 1, action.id)
        # 篡改 meaning
        sigs[0].meaning = "tampered"
        assert service.verify_signature_chain(sigs) is False


@pytest.mark.unit
class TestSla:
    async def test_create_sla(self, db_session):
        sla = await service.create_sla(
            db_session, 1, SlaCreate(action_type=ActionType.HOLD, target_minutes=60, warning_minutes=30)
        )
        assert sla.target_minutes == 60

    async def test_duplicate_sla_conflict(self, db_session):
        await service.create_sla(db_session, 1, SlaCreate(action_type=ActionType.HOLD, target_minutes=60))
        with pytest.raises(ConflictError):
            await service.create_sla(
                db_session, 1, SlaCreate(action_type=ActionType.HOLD, target_minutes=120)
            )

    async def test_sla_breach_detection(self, db_session):
        # SLA: hold 60 分钟
        await service.create_sla(
            db_session, 1, SlaCreate(action_type=ActionType.HOLD, target_minutes=60, escalation_role="supervisor")
        )
        # 创建一个已过期的行动
        action = await service.create_action(
            db_session, 1,
            ActionCreate(
                event_id=1, type=ActionType.HOLD,
                due_at=utcnow() - timedelta(minutes=30),  # 已超时 30 分钟
            ),
        )
        breaches = await service.check_sla_breaches(db_session, 1)
        assert len(breaches) == 1
        assert breaches[0].action_id == action.id
        assert breaches[0].overdue_minutes >= 29
        assert breaches[0].escalation_role == "supervisor"


@pytest.mark.unit
class TestBatchDisposition:
    async def test_dispose_batch_with_mock(self, db_session, fake_integrations):
        from app.integrations.fake.store import FakeStore

        store = FakeStore.empty()
        store.batches["B001"] = __import__(
            "app.integrations.dtos", fromlist=["BatchDTO"]
        ).BatchDTO(batch_id="B001", product="P1")
        from app.integrations.fake.mes import FakeMesClient

        mes = FakeMesClient(store)
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        rec = await service.dispose_batch(
            db_session, 1, action.id,
            BatchDispositionRequest(batch_id="B001", disposition=BatchDisposition.HOLD, reason="漂移"),
            mes_client=mes,
        )
        assert rec.synced is True
        assert rec.disposition == "hold"
        assert store.batches["B001"].status == "held"

    async def test_dispose_batch_no_client(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        rec = await service.dispose_batch(
            db_session, 1, action.id,
            BatchDispositionRequest(batch_id="B002", disposition=BatchDisposition.RELEASE),
            mes_client=None,
        )
        assert rec.synced is False


@pytest.mark.unit
class TestClosureValidation:
    async def test_validate_closure(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        await service.execute_action(db_session, 1, action.id, actor_id=2)
        cv = await service.validate_closure(
            db_session, 1, action.id, 3,
            ClosureRequest(passed=True, note="复测合格", evidence={"retest": "pass"}),
        )
        assert cv.passed is True

    async def test_validate_non_completed_conflict(self, db_session):
        action = await service.create_action(
            db_session, 1, ActionCreate(event_id=1, type=ActionType.HOLD)
        )
        with pytest.raises(ConflictError):
            await service.validate_closure(
                db_session, 1, action.id, 2, ClosureRequest(passed=True)
            )


@pytest.mark.unit
class TestActionAPI:
    async def test_action_lifecycle_via_api(self, authed_client):
        create = await authed_client.post(
            "/api/v1/actions",
            json={"event_id": 1, "type": "hold", "title": "Hold", "description": "漂移"},
        )
        assert create.status_code == 201, create.text
        aid = create.json()["id"]

        execute = await authed_client.post(
            f"/api/v1/actions/{aid}/execute", json={"detail": "已执行"}
        )
        assert execute.status_code == 200
        assert execute.json()["status"] == "completed"

        sign = await authed_client.post(
            f"/api/v1/actions/{aid}/signatures", json={"meaning": "approve"}
        )
        assert sign.status_code == 201
        assert sign.json()["signature_hash"]

        sigs = await authed_client.get(f"/api/v1/actions/{aid}/signatures")
        assert len(sigs.json()) == 1

    async def test_sla_via_api(self, authed_client):
        create = await authed_client.post(
            "/api/v1/actions/slas",
            json={"action_type": "hold", "target_minutes": 120, "warning_minutes": 60},
        )
        assert create.status_code == 201
        listed = await authed_client.get("/api/v1/actions/slas")
        assert len(listed.json()) >= 1
