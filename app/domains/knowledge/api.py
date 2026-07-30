"""BP-F 知识管理域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.knowledge import service
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

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ----- 案例 -----


@router.post("/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:knowledge:publish")),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    case = await service.create_case(db, tenant_id, payload)
    await db.commit()
    return service.case_to_out(case)


@router.get("/cases", response_model=list[CaseOut])
async def list_cases(
    status: str | None = None,
    equipment_id: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:knowledge:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_cases(
        db, tenant_id, status=status, equipment_id=equipment_id, page=page, size=size
    )
    return result.items


@router.get("/cases/{case_id}", response_model=CaseOut)
async def get_case(
    case_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:knowledge:read")),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    case = await service.get_case(db, tenant_id, case_id)
    return service.case_to_out(case)


@router.patch("/cases/{case_id}", response_model=CaseOut)
async def update_case(
    case_id: int,
    payload: CaseUpdate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:knowledge:publish")),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    case = await service.update_case(db, tenant_id, case_id, payload)
    await db.commit()
    return service.case_to_out(case)


@router.post("/cases/{case_id}/publish", response_model=CaseOut)
async def publish_case(
    case_id: int,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:knowledge:publish")),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    case = await service.publish_case(db, tenant_id, case_id, user.id)
    await db.commit()
    return service.case_to_out(case)


@router.post("/cases/recommend", response_model=list[CaseSearchResult])
async def recommend_cases(
    payload: dict,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:knowledge:read")),
    db: AsyncSession = Depends(get_db),
):
    return await service.recommend_similar(db, tenant_id, payload.get("context", {}))


# ----- 处置方案模板 -----


@router.post("/templates", response_model=SolutionTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: SolutionTemplateCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:knowledge:publish")),
    db: AsyncSession = Depends(get_db),
) -> SolutionTemplateOut:
    tpl = await service.create_template(db, tenant_id, payload)
    await db.commit()
    return service.template_to_out(tpl)


@router.get("/templates", response_model=list[SolutionTemplateOut])
async def list_templates(
    anomaly_type: str | None = None,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tpls = await service.list_templates(db, tenant_id, anomaly_type=anomaly_type)
    return [service.template_to_out(t) for t in tpls]


# ----- 知识图谱 -----


@router.post("/graph/nodes", response_model=GraphNodeOut, status_code=status.HTTP_201_CREATED)
async def create_graph_node(
    payload: GraphNodeCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:knowledge:publish")),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeOut:
    node = await service.create_graph_node(db, tenant_id, payload)
    await db.commit()
    return GraphNodeOut.model_validate(node)


@router.get("/graph/nodes", response_model=list[GraphNodeOut])
async def list_graph_nodes(
    node_type: str | None = None,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    nodes = await service.list_graph_nodes(db, tenant_id, node_type=node_type)
    return [GraphNodeOut.model_validate(n) for n in nodes]
