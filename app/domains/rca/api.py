"""BP-C 根因分析域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.rca import service
from app.domains.rca.schemas import (
    CpmRequest,
    CpmResult,
    DataCorrelationEntry,
    DataCorrelationOut,
    FishboneEntry,
    FishboneOut,
    FiveWhyEntry,
    FiveWhyOut,
    RcaCreate,
    RcaOut,
    RcaUpdate,
    RepeatResult,
)

router = APIRouter(prefix="/rcas", tags=["rcas"])


@router.post("", response_model=RcaOut, status_code=status.HTTP_201_CREATED)
async def create_rca(
    payload: RcaCreate,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:rca:create")),
    db: AsyncSession = Depends(get_db),
) -> RcaOut:
    rca = await service.create_rca(db, tenant_id, payload, user.id)
    await db.commit()
    return service.rca_to_out(rca)


@router.get("", response_model=list[RcaOut])
async def list_rcas(
    event_id: int | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_rcas(db, tenant_id, event_id=event_id, status=status, page=page, size=size)
    return result.items


@router.get("/{rca_id}", response_model=RcaOut)
async def get_rca(
    rca_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:read")),
    db: AsyncSession = Depends(get_db),
) -> RcaOut:
    rca = await service.get_rca(db, tenant_id, rca_id)
    return service.rca_to_out(rca)


@router.patch("/{rca_id}", response_model=RcaOut)
async def update_rca(
    rca_id: int,
    payload: RcaUpdate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:create")),
    db: AsyncSession = Depends(get_db),
) -> RcaOut:
    rca = await service.update_rca(db, tenant_id, rca_id, payload)
    await db.commit()
    return service.rca_to_out(rca)


# ----- 5-Why -----


@router.post("/{rca_id}/five-why", response_model=FiveWhyOut, status_code=status.HTTP_201_CREATED)
async def add_five_why(
    rca_id: int,
    payload: FiveWhyEntry,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:create")),
    db: AsyncSession = Depends(get_db),
) -> FiveWhyOut:
    entry = await service.add_five_why(db, tenant_id, rca_id, payload)
    await db.commit()
    return FiveWhyOut.model_validate(entry)


@router.get("/{rca_id}/five-why", response_model=list[FiveWhyOut])
async def list_five_why(
    rca_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:read")),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_five_why(db, tenant_id, rca_id)
    return [FiveWhyOut.model_validate(i) for i in items]


# ----- 鱼骨图 -----


@router.post("/{rca_id}/fishbone", response_model=FishboneOut, status_code=status.HTTP_201_CREATED)
async def add_fishbone(
    rca_id: int,
    payload: FishboneEntry,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:create")),
    db: AsyncSession = Depends(get_db),
) -> FishboneOut:
    entry = await service.add_fishbone(db, tenant_id, rca_id, payload)
    await db.commit()
    return FishboneOut.model_validate(entry)


@router.get("/{rca_id}/fishbone", response_model=list[FishboneOut])
async def list_fishbone(
    rca_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:read")),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_fishbone(db, tenant_id, rca_id)
    return [FishboneOut.model_validate(i) for i in items]


# ----- 数据关联 -----


@router.post("/{rca_id}/correlations", response_model=DataCorrelationOut, status_code=status.HTTP_201_CREATED)
async def add_correlation(
    rca_id: int,
    payload: DataCorrelationEntry,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:create")),
    db: AsyncSession = Depends(get_db),
) -> DataCorrelationOut:
    entry = await service.add_correlation(db, tenant_id, rca_id, payload)
    await db.commit()
    return DataCorrelationOut.model_validate(entry)


@router.get("/{rca_id}/correlations", response_model=list[DataCorrelationOut])
async def list_correlations(
    rca_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:read")),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_correlations(db, tenant_id, rca_id)
    return [DataCorrelationOut.model_validate(i) for i in items]


# ----- CPM -----


@router.post("/cpm", response_model=CpmResult)
async def run_cpm(
    payload: CpmRequest,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:create")),
    db: AsyncSession = Depends(get_db),
) -> CpmResult:
    # 自动从 knowledge 域的已发布案例提取候选
    from app.domains.knowledge.models import KnowledgeCase
    from app.domains.common.enums import KnowledgeCaseStatus
    from sqlalchemy import select as _select

    stmt = _select(KnowledgeCase).where(
        KnowledgeCase.tenant_id == tenant_id,
        KnowledgeCase.status == KnowledgeCaseStatus.PUBLISHED.value,
    )
    cases = (await db.execute(stmt)).scalars().all()
    candidates = []
    for c in cases:
        ctx = dict(c.context or {})
        ctx["case_id"] = c.id
        # 把 equipment_id / process_step 提升到顶层，便于 CPM 打分
        for k in ("equipment_id", "process_step"):
            if getattr(c, k, None) and k not in ctx:
                ctx[k] = getattr(c, k)
        candidates.append(ctx)
    run = await service.run_cpm(db, tenant_id, payload, candidates=candidates or None)
    await db.commit()
    return service.cpm_to_out(run)


# ----- 重复异常识别 -----


@router.post("/repeat-detection", response_model=RepeatResult)
async def detect_repeat(
    payload: dict,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:rca:create")),
    db: AsyncSession = Depends(get_db),
) -> RepeatResult:
    from app.utils.time import utcnow

    result = await service.detect_repeat(
        db,
        tenant_id,
        payload["event_id"],
        payload["fingerprint"],
        utcnow(),
    )
    await db.commit()
    return result
