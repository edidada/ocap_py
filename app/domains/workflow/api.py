"""BP-B 工作流编排域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.workflow import service
from app.domains.workflow.schemas import (
    AdvanceRequest,
    AdvanceResult,
    InstanceOut,
    InterveneRequest,
    NodeOut,
    SopCreate,
    SopOut,
    StartInstance,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ----------------------------- 模板 -----------------------------


@router.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:workflow:publish")),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    tpl = await service.create_template(db, tenant_id, payload)
    await db.commit()
    return service.template_to_out(tpl)


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_templates(db, tenant_id, status=status, page=page, size=size)
    return result.items


@router.get("/templates/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    tpl = await service.get_template(db, tenant_id, template_id)
    return service.template_to_out(tpl)


@router.patch("/templates/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    payload: TemplateUpdate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:workflow:publish")),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    tpl = await service.update_template(db, tenant_id, template_id, payload)
    await db.commit()
    return service.template_to_out(tpl)


@router.post("/templates/{template_id}/publish", response_model=TemplateOut)
async def publish_template(
    template_id: int,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:workflow:publish")),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    tpl = await service.publish_template(db, tenant_id, template_id, published_by=user.id)
    await db.commit()
    return service.template_to_out(tpl)


# ----------------------------- 实例 -----------------------------


@router.post("/instances", response_model=InstanceOut, status_code=status.HTTP_201_CREATED)
async def start_instance(
    payload: StartInstance,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:workflow:advance")),
    db: AsyncSession = Depends(get_db),
) -> InstanceOut:
    inst = await service.start_instance(db, tenant_id, payload)
    await db.commit()
    return InstanceOut.model_validate(inst)


@router.get("/instances", response_model=list[InstanceOut])
async def list_instances(
    status: str | None = None,
    event_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_instances(
        db, tenant_id, status=status, event_id=event_id, page=page, size=size
    )
    return result.items


@router.get("/instances/{instance_id}", response_model=InstanceOut)
async def get_instance(
    instance_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InstanceOut:
    inst = await service.get_instance(db, tenant_id, instance_id)
    return InstanceOut.model_validate(inst)


@router.get("/instances/{instance_id}/nodes", response_model=list[NodeOut])
async def list_nodes(
    instance_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    nodes = await service.list_nodes(db, tenant_id, instance_id)
    return [NodeOut.model_validate(n) for n in nodes]


@router.post("/instances/{instance_id}/advance", response_model=AdvanceResult)
async def advance_instance(
    instance_id: int,
    payload: AdvanceRequest,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:workflow:advance")),
    db: AsyncSession = Depends(get_db),
) -> AdvanceResult:
    result = await service.advance_instance(db, tenant_id, instance_id, payload)
    await db.commit()
    return result


@router.post("/instances/{instance_id}/intervene", response_model=InstanceOut)
async def intervene(
    instance_id: int,
    payload: InterveneRequest,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:workflow:intervene")),
    db: AsyncSession = Depends(get_db),
) -> InstanceOut:
    inst = await service.intervene(db, tenant_id, instance_id, payload, user.id)
    await db.commit()
    return InstanceOut.model_validate(inst)


# ----------------------------- SOP -----------------------------


@router.post("/sops", response_model=SopOut, status_code=status.HTTP_201_CREATED)
async def create_sop(
    payload: SopCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:workflow:publish")),
    db: AsyncSession = Depends(get_db),
) -> SopOut:
    sop = await service.create_sop(db, tenant_id, payload)
    await db.commit()
    return service.sop_to_out(sop)


@router.get("/sops", response_model=list[SopOut])
async def list_sops(
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sops = await service.list_sops(db, tenant_id)
    return [service.sop_to_out(s) for s in sops]


@router.get("/sops/{sop_id}", response_model=SopOut)
async def get_sop(
    sop_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SopOut:
    sop = await service.get_sop(db, tenant_id, sop_id)
    return service.sop_to_out(sop)
