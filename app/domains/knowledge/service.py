"""BP-F 知识管理域服务。

- 案例库 CRUD + 发布版本化（BP-F-01/06）
- 经验复用：基于上下文特征匹配已发布案例（BP-F-03）
- 处置方案模板库（BP-F-04）
- 知识图谱节点/边管理（BP-F-02，P2）
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page
from app.domains.common.enums import KnowledgeCaseStatus
from app.domains.knowledge.models import (
    ExpertRule,
    KnowledgeCase,
    KnowledgeCaseVersion,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    SolutionTemplate,
)
from app.domains.knowledge.schemas import (
    CaseCreate,
    CaseOut,
    CaseSearchResult,
    CaseUpdate,
    GraphEdgeCreate,
    GraphNodeCreate,
    GraphNodeOut,
    SolutionTemplateCreate,
    SolutionTemplateOut,
)
from app.utils.time import utcnow

# 经验复用匹配特征权重
_MATCH_WEIGHTS: dict[str, int] = {
    "equipment_id": 35,
    "process_step": 25,
    "anomaly_type": 25,
    "severity": 15,
}


# ----------------------------- 案例 -----------------------------


async def create_case(db: AsyncSession, tenant_id: int, payload: CaseCreate) -> KnowledgeCase:
    existing = (
        await db.execute(
            select(KnowledgeCase).where(
                KnowledgeCase.tenant_id == tenant_id, KnowledgeCase.code == payload.code
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"案例编码已存在: {payload.code}")
    case = KnowledgeCase(
        tenant_id=tenant_id,
        code=payload.code,
        title=payload.title,
        event_id=payload.event_id,
        equipment_id=payload.equipment_id,
        process_step=payload.process_step,
        anomaly_type=payload.anomaly_type,
        root_cause=payload.root_cause,
        solution=payload.solution,
        context=payload.context,
    )
    db.add(case)
    await db.flush()
    return case


async def get_case(db: AsyncSession, tenant_id: int, case_id: int) -> KnowledgeCase:
    case = await db.get(KnowledgeCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise NotFoundError(f"案例不存在: {case_id}")
    return case


async def list_cases(
    db: AsyncSession,
    tenant_id: int,
    *,
    status: str | None = None,
    equipment_id: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[CaseOut]:
    stmt = select(KnowledgeCase).where(KnowledgeCase.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(KnowledgeCase.status == status)
    if equipment_id:
        stmt = stmt.where(KnowledgeCase.equipment_id == equipment_id)
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(KnowledgeCase.id.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of([CaseOut.model_validate(i) for i in items], total, page, size)


async def update_case(
    db: AsyncSession, tenant_id: int, case_id: int, payload: CaseUpdate
) -> KnowledgeCase:
    case = await get_case(db, tenant_id, case_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(case, k, v.value if hasattr(v, "value") else v)
    await db.flush()
    return case


async def publish_case(
    db: AsyncSession, tenant_id: int, case_id: int, published_by: int
) -> KnowledgeCase:
    """发布案例，生成版本快照（BP-F-06 版本管理）。"""
    case = await get_case(db, tenant_id, case_id)
    case.version += 1
    case.status = KnowledgeCaseStatus.PUBLISHED.value
    case.published_at = utcnow()
    case.published_by = published_by
    db.add(
        KnowledgeCaseVersion(
            case_id=case.id,
            version=case.version,
            snapshot={
                "title": case.title,
                "root_cause": case.root_cause,
                "solution": case.solution,
                "context": case.context,
                "equipment_id": case.equipment_id,
                "process_step": case.process_step,
                "anomaly_type": case.anomaly_type,
            },
            change_log=f"published by {published_by}",
        )
    )
    await db.flush()
    return case


def case_to_out(case: KnowledgeCase) -> CaseOut:
    return CaseOut.model_validate(case)


# ----------------------------- 经验复用（BP-F-03）-----------------------------


async def recommend_similar(
    db: AsyncSession, tenant_id: int, context: dict, limit: int = 5
) -> list[CaseSearchResult]:
    """基于上下文特征匹配已发布案例，返回相似度排序结果。"""
    stmt = select(KnowledgeCase).where(
        KnowledgeCase.tenant_id == tenant_id,
        KnowledgeCase.status == KnowledgeCaseStatus.PUBLISHED.value,
    )
    cases = (await db.execute(stmt)).scalars().all()
    scored: list[CaseSearchResult] = []
    for c in cases:
        total = 0
        matched = 0
        feats: list[str] = []
        for feat, weight in _MATCH_WEIGHTS.items():
            cv = c.context.get(feat) or getattr(c, feat, None)
            qv = context.get(feat)
            if qv is None or cv is None:
                continue
            total += weight
            if qv == cv:
                matched += weight
                feats.append(feat)
        if total == 0:
            continue
        score = round(matched / total * 100)
        if score > 0:
            scored.append(CaseSearchResult(case=CaseOut.model_validate(c), score=score, matched_features=feats))
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:limit]


# ----------------------------- 处置方案模板 -----------------------------


async def create_template(
    db: AsyncSession, tenant_id: int, payload: SolutionTemplateCreate
) -> SolutionTemplate:
    existing = (
        await db.execute(
            select(SolutionTemplate).where(
                SolutionTemplate.tenant_id == tenant_id, SolutionTemplate.code == payload.code
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"模板编码已存在: {payload.code}")
    tpl = SolutionTemplate(
        tenant_id=tenant_id,
        code=payload.code,
        title=payload.title,
        anomaly_type=payload.anomaly_type,
        steps=payload.steps,
        applicable_context=payload.applicable_context,
        enabled=payload.enabled,
    )
    db.add(tpl)
    await db.flush()
    return tpl


async def list_templates(
    db: AsyncSession, tenant_id: int, anomaly_type: str | None = None
) -> list[SolutionTemplate]:
    stmt = select(SolutionTemplate).where(SolutionTemplate.tenant_id == tenant_id)
    if anomaly_type:
        stmt = stmt.where(SolutionTemplate.anomaly_type == anomaly_type)
    return list((await db.execute(stmt)).scalars().all())


def template_to_out(tpl: SolutionTemplate) -> SolutionTemplateOut:
    return SolutionTemplateOut.model_validate(tpl)


# ----------------------------- 知识图谱（P2）-----------------------------


async def create_graph_node(
    db: AsyncSession, tenant_id: int, payload: GraphNodeCreate
) -> KnowledgeGraphNode:
    node = KnowledgeGraphNode(
        tenant_id=tenant_id,
        node_type=payload.node_type,
        name=payload.name,
        attributes=payload.attributes,
    )
    db.add(node)
    await db.flush()
    return node


async def list_graph_nodes(db: AsyncSession, tenant_id: int, node_type: str | None = None) -> list[KnowledgeGraphNode]:
    stmt = select(KnowledgeGraphNode).where(KnowledgeGraphNode.tenant_id == tenant_id)
    if node_type:
        stmt = stmt.where(KnowledgeGraphNode.node_type == node_type)
    return list((await db.execute(stmt)).scalars().all())


async def create_graph_edge(
    db: AsyncSession, tenant_id: int, payload: GraphEdgeCreate
) -> KnowledgeGraphEdge:
    edge = KnowledgeGraphEdge(
        tenant_id=tenant_id,
        from_node_id=payload.from_node_id,
        to_node_id=payload.to_node_id,
        relation=payload.relation,
        weight=payload.weight,
    )
    db.add(edge)
    await db.flush()
    return edge


async def list_graph_edges(db: AsyncSession, tenant_id: int) -> list[KnowledgeGraphEdge]:
    stmt = select(KnowledgeGraphEdge).where(KnowledgeGraphEdge.tenant_id == tenant_id)
    return list((await db.execute(stmt)).scalars().all())
