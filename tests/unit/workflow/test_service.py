"""BP-B 工作流域 service + API 测试。"""

from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, ValidationFailed
from app.domains.common.enums import WorkflowInstanceStatus, WorkflowTemplateStatus
from app.domains.workflow import service
from app.domains.workflow.schemas import (
    AdvanceRequest,
    InterveneRequest,
    SopCreate,
    StartInstance,
    TemplateCreate,
)


def _serial_definition() -> dict:
    return {
        "initial": "start",
        "nodes": [
            {"key": "start", "type": "start", "name": "开始"},
            {"key": "investigate", "type": "task", "name": "排查", "assignee_role": "engineer"},
            {"key": "fix", "type": "task", "name": "处置", "assignee_role": "engineer"},
            {"key": "end", "type": "end", "name": "结束"},
        ],
        "transitions": [
            {"from": "start", "to": "investigate"},
            {"from": "investigate", "to": "fix"},
            {"from": "fix", "to": "end"},
        ],
    }


def _decision_definition() -> dict:
    return {
        "initial": "start",
        "nodes": [
            {"key": "start", "type": "start"},
            {"key": "decide", "type": "decision", "name": "严重度判定"},
            {"key": "minor_end", "type": "end", "name": "轻微结束"},
            {"key": "major_fix", "type": "task", "name": "重大处置"},
            {"key": "major_end", "type": "end"},
        ],
        "transitions": [
            {"from": "start", "to": "decide"},
            {"from": "decide", "to": "minor_end", "label": "minor"},
            {"from": "decide", "to": "major_fix", "label": "major"},
            {"from": "major_fix", "to": "major_end"},
        ],
    }


@pytest.mark.unit
class TestTemplateService:
    async def test_create_and_get_template(self, db_session):
        tpl = await service.create_template(
            db_session, 1, TemplateCreate(code="wf-1", name="流程1", definition=_serial_definition())
        )
        assert tpl.id is not None
        assert tpl.status == WorkflowTemplateStatus.DRAFT.value
        got = await service.get_template(db_session, 1, tpl.id)
        assert got.code == "wf-1"

    async def test_create_duplicate_code_conflict(self, db_session):
        await service.create_template(
            db_session, 1, TemplateCreate(code="wf-dup", definition=_serial_definition())
        )
        with pytest.raises(ConflictError):
            await service.create_template(
                db_session, 1, TemplateCreate(code="wf-dup", definition=_serial_definition())
            )

    async def test_invalid_definition_raises(self, db_session):
        with pytest.raises(ValidationFailed):
            await service.create_template(
                db_session,
                1,
                TemplateCreate(code="bad", definition={"initial": "x", "nodes": [], "transitions": []}),
            )

    async def test_publish_template(self, db_session):
        tpl = await service.create_template(
            db_session, 1, TemplateCreate(code="wf-pub", definition=_serial_definition())
        )
        published = await service.publish_template(db_session, 1, tpl.id, published_by=2)
        assert published.status == WorkflowTemplateStatus.PUBLISHED.value
        assert published.version == 1
        assert published.published_at is not None


@pytest.mark.unit
class TestInstanceService:
    async def test_start_instance_requires_published(self, db_session):
        tpl = await service.create_template(
            db_session, 1, TemplateCreate(code="wf-start", definition=_serial_definition())
        )
        with pytest.raises(ConflictError):
            await service.start_instance(db_session, 1, StartInstance(template_id=tpl.id))

    async def test_serial_full_run(self, db_session):
        tpl = await service.create_template(
            db_session, 1, TemplateCreate(code="wf-serial", definition=_serial_definition())
        )
        await service.publish_template(db_session, 1, tpl.id, published_by=2)
        inst = await service.start_instance(db_session, 1, StartInstance(template_id=tpl.id))
        assert inst.status == WorkflowInstanceStatus.RUNNING.value
        assert inst.current_node_key == "investigate"

        # 推进 investigate -> fix
        r1 = await service.advance_instance(
            db_session, 1, inst.id,
            AdvanceRequest(action="complete_task", node_key="investigate", output={"found": "drift"}),
        )
        assert r1.activated_nodes == ["fix"]
        assert not r1.terminal

        # 推进 fix -> end
        r2 = await service.advance_instance(
            db_session, 1, inst.id,
            AdvanceRequest(action="complete_task", node_key="fix", output={"action": "reset"}),
        )
        assert r2.terminal
        assert r2.instance.status == WorkflowInstanceStatus.COMPLETED.value
        assert r2.instance.completed_at is not None

    async def test_decision_manual_choice(self, db_session):
        tpl = await service.create_template(
            db_session, 1, TemplateCreate(code="wf-dec", definition=_decision_definition())
        )
        await service.publish_template(db_session, 1, tpl.id, published_by=2)
        inst = await service.start_instance(db_session, 1, StartInstance(template_id=tpl.id))
        # decide 节点无 guard 自动匹配，保持活跃
        r = await service.advance_instance(
            db_session, 1, inst.id,
            AdvanceRequest(action="take_decision", node_key="decide", choice="major"),
        )
        assert r.activated_nodes == ["major_fix"]
        assert not r.terminal
        # 完成 major_fix -> major_end
        r2 = await service.advance_instance(
            db_session, 1, inst.id,
            AdvanceRequest(action="complete_task", node_key="major_fix"),
        )
        assert r2.terminal

    async def test_skip_intervention(self, db_session):
        tpl = await service.create_template(
            db_session, 1, TemplateCreate(code="wf-skip", definition=_serial_definition())
        )
        await service.publish_template(db_session, 1, tpl.id, published_by=2)
        inst = await service.start_instance(db_session, 1, StartInstance(template_id=tpl.id))
        result = await service.intervene(
            db_session, 1, inst.id,
            InterveneRequest(type="skip", node_key="investigate", reason="无需排查"),
            actor_user_id=2,
        )
        assert result.status == WorkflowInstanceStatus.RUNNING.value

    async def test_list_nodes(self, db_session):
        tpl = await service.create_template(
            db_session, 1, TemplateCreate(code="wf-nodes", definition=_serial_definition())
        )
        await service.publish_template(db_session, 1, tpl.id, published_by=2)
        inst = await service.start_instance(db_session, 1, StartInstance(template_id=tpl.id))
        nodes = await service.list_nodes(db_session, 1, inst.id)
        assert len(nodes) == 4
        keys = {n.node_key for n in nodes}
        assert keys == {"start", "investigate", "fix", "end"}
        # investigate 应为 active
        inv = next(n for n in nodes if n.node_key == "investigate")
        assert inv.status == "active"


@pytest.mark.unit
class TestSopService:
    async def test_sop_crud(self, db_session):
        sop = await service.create_sop(
            db_session, 1, SopCreate(code="sop-1", title="SOP", steps=["步骤1", "步骤2"])
        )
        assert sop.id is not None
        sops = await service.list_sops(db_session, 1)
        assert len(sops) == 1
        got = await service.get_sop(db_session, 1, sop.id)
        assert got.steps == ["步骤1", "步骤2"]

    async def test_sop_duplicate_conflict(self, db_session):
        await service.create_sop(db_session, 1, SopCreate(code="sop-dup", title="SOP", steps=[]))
        with pytest.raises(ConflictError):
            await service.create_sop(db_session, 1, SopCreate(code="sop-dup", title="SOP2", steps=[]))


@pytest.mark.unit
class TestWorkflowAPI:
    async def test_template_crud_via_api(self, authed_client):
        create = await authed_client.post(
            "/api/v1/workflows/templates",
            json={"code": "api-wf", "name": "API流程", "definition": _serial_definition()},
        )
        assert create.status_code == 201, create.text
        tid = create.json()["id"]

        listed = await authed_client.get("/api/v1/workflows/templates")
        assert any(t["code"] == "api-wf" for t in listed.json())

        got = await authed_client.get(f"/api/v1/workflows/templates/{tid}")
        assert got.status_code == 200

        published = await authed_client.post(f"/api/v1/workflows/templates/{tid}/publish")
        assert published.status_code == 200
        assert published.json()["status"] == "published"

    async def test_instance_lifecycle_via_api(self, authed_client):
        create = await authed_client.post(
            "/api/v1/workflows/templates",
            json={"code": "api-wf-life", "definition": _serial_definition()},
        )
        tid = create.json()["id"]
        await authed_client.post(f"/api/v1/workflows/templates/{tid}/publish")

        start = await authed_client.post(
            "/api/v1/workflows/instances", json={"template_id": tid}
        )
        assert start.status_code == 201, start.text
        iid = start.json()["id"]
        assert start.json()["current_node_key"] == "investigate"

        nodes = await authed_client.get(f"/api/v1/workflows/instances/{iid}/nodes")
        assert nodes.status_code == 200
        assert len(nodes.json()) == 4

        adv = await authed_client.post(
            f"/api/v1/workflows/instances/{iid}/advance",
            json={"action": "complete_task", "node_key": "investigate", "output": {"x": 1}},
        )
        assert adv.status_code == 200
        assert adv.json()["activated_nodes"] == ["fix"]

        adv2 = await authed_client.post(
            f"/api/v1/workflows/instances/{iid}/advance",
            json={"action": "complete_task", "node_key": "fix"},
        )
        assert adv2.json()["terminal"] is True
        assert adv2.json()["instance"]["status"] == "completed"

    async def test_sop_via_api(self, authed_client):
        create = await authed_client.post(
            "/api/v1/workflows/sops",
            json={"code": "api-sop", "title": "API SOP", "steps": ["a", "b"]},
        )
        assert create.status_code == 201
        listed = await authed_client.get("/api/v1/workflows/sops")
        assert any(s["code"] == "api-sop" for s in listed.json())
