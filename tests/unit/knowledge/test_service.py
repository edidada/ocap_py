"""BP-F 知识管理域 service + API 测试。"""

from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.common.enums import KnowledgeCaseStatus
from app.domains.knowledge import service
from app.domains.knowledge.schemas import (
    CaseCreate,
    CaseUpdate,
    GraphEdgeCreate,
    GraphNodeCreate,
    SolutionTemplateCreate,
)


@pytest.mark.unit
class TestCaseService:
    async def test_create_and_get_case(self, db_session):
        case = await service.create_case(
            db_session, 1,
            CaseCreate(code="k-1", title="案例1", equipment_id="EQP-01", root_cause="漂移", solution="调整"),
        )
        assert case.id is not None
        assert case.status == KnowledgeCaseStatus.DRAFT.value
        got = await service.get_case(db_session, 1, case.id)
        assert got.code == "k-1"

    async def test_duplicate_case_conflict(self, db_session):
        await service.create_case(db_session, 1, CaseCreate(code="k-dup", title="x"))
        with pytest.raises(ConflictError):
            await service.create_case(db_session, 1, CaseCreate(code="k-dup", title="y"))

    async def test_publish_case_versioning(self, db_session):
        case = await service.create_case(db_session, 1, CaseCreate(code="k-pub", title="x"))
        published = await service.publish_case(db_session, 1, case.id, published_by=2)
        assert published.status == KnowledgeCaseStatus.PUBLISHED.value
        assert published.version == 1
        assert published.published_at is not None

    async def test_update_case(self, db_session):
        case = await service.create_case(db_session, 1, CaseCreate(code="k-upd", title="x"))
        updated = await service.update_case(
            db_session, 1, case.id, CaseUpdate(root_cause="新根因", solution="新方案")
        )
        assert updated.root_cause == "新根因"

    async def test_get_case_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            await service.get_case(db_session, 1, 9999)


@pytest.mark.unit
class TestRecommendSimilar:
    async def test_recommend_matches(self, db_session):
        # 创建并发布两个案例
        c1 = await service.create_case(
            db_session, 1,
            CaseCreate(code="r-1", equipment_id="EQP-01", process_step="etch", anomaly_type="drift",
                       context={"equipment_id": "EQP-01", "process_step": "etch"}),
        )
        await service.publish_case(db_session, 1, c1.id, 2)
        c2 = await service.create_case(
            db_session, 1,
            CaseCreate(code="r-2", equipment_id="EQP-02", process_step="litho", anomaly_type="shift",
                       context={"equipment_id": "EQP-02", "process_step": "litho"}),
        )
        await service.publish_case(db_session, 1, c2.id, 2)
        results = await service.recommend_similar(
            db_session, 1,
            {"equipment_id": "EQP-01", "process_step": "etch", "anomaly_type": "drift"},
        )
        assert len(results) >= 1
        assert results[0].case.code == "r-1"
        assert results[0].score == 100

    async def test_recommend_no_published(self, db_session):
        await service.create_case(db_session, 1, CaseCreate(code="r-draft", equipment_id="EQP-01"))
        results = await service.recommend_similar(db_session, 1, {"equipment_id": "EQP-01"})
        assert len(results) == 0


@pytest.mark.unit
class TestSolutionTemplate:
    async def test_template_crud(self, db_session):
        tpl = await service.create_template(
            db_session, 1,
            SolutionTemplateCreate(code="sol-1", title="方案1", anomaly_type="drift", steps=["步骤1", "步骤2"]),
        )
        assert tpl.id is not None
        tpls = await service.list_templates(db_session, 1)
        assert len(tpls) == 1
        filtered = await service.list_templates(db_session, 1, anomaly_type="drift")
        assert len(filtered) == 1
        none = await service.list_templates(db_session, 1, anomaly_type="other")
        assert len(none) == 0


@pytest.mark.unit
class TestKnowledgeGraph:
    async def test_graph_nodes_and_edges(self, db_session):
        n1 = await service.create_graph_node(
            db_session, 1, GraphNodeCreate(node_type="equipment", name="EQP-01")
        )
        n2 = await service.create_graph_node(
            db_session, 1, GraphNodeCreate(node_type="anomaly", name="drift")
        )
        edge = await service.create_graph_edge(
            db_session, 1, GraphEdgeCreate(from_node_id=n1.id, to_node_id=n2.id, relation="causes")
        )
        nodes = await service.list_graph_nodes(db_session, 1)
        assert len(nodes) == 2
        edges = await service.list_graph_edges(db_session, 1)
        assert len(edges) == 1
        assert edges[0].relation == "causes"


@pytest.mark.unit
class TestKnowledgeAPI:
    async def test_case_lifecycle_via_api(self, authed_client):
        create = await authed_client.post(
            "/api/v1/knowledge/cases",
            json={"code": "api-k", "title": "API案例", "equipment_id": "EQP-01", "root_cause": "x", "solution": "y"},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        published = await authed_client.post(f"/api/v1/knowledge/cases/{cid}/publish")
        assert published.status_code == 200
        assert published.json()["status"] == "published"

        rec = await authed_client.post(
            "/api/v1/knowledge/cases/recommend", json={"context": {"equipment_id": "EQP-01"}}
        )
        assert rec.status_code == 200
        assert len(rec.json()) >= 1

    async def test_template_via_api(self, authed_client):
        create = await authed_client.post(
            "/api/v1/knowledge/templates",
            json={"code": "api-sol", "title": "方案", "steps": ["a"]},
        )
        assert create.status_code == 201
        listed = await authed_client.get("/api/v1/knowledge/templates")
        assert any(t["code"] == "api-sol" for t in listed.json())
