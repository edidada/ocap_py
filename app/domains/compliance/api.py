"""BP-H 合规与审计域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.core.pagination import PageParams
from app.db.session import get_db
from app.domains.common.enums import AuditAction, ConfigItemScope
from app.domains.compliance import service
from app.domains.compliance.schemas import (
    ConfigItemIn,
    ConfigItemOut,
    RetentionPolicyIn,
    RetentionPolicyOut,
    SpcSpecIn,
    SpcSpecOut,
)
from app.domains.iam.models import User

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/audits")
async def list_audits(
    resource_type: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("iam:auditor")),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_audits(
        db, tenant_id, PageParams(page=page, size=min(page_size, 200)),
        resource_type=resource_type, action=action, user_id=user_id,
    )


@router.get("/audits/verify", response_model=dict)
async def verify_audit(
    limit: int = Query(500, ge=10, le=5000),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("iam:auditor")),
    db: AsyncSession = Depends(get_db),
):
    broken = await service.verify_audit_chain(db, tenant_id, limit=limit)
    return {"broken_ids": broken, "intact": len(broken) == 0}


@router.get("/retention", response_model=list[RetentionPolicyOut])
async def list_retention(
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("iam:auditor")),
    db: AsyncSession = Depends(get_db),
):
    return [service.retention_to_out(p) for p in await service.list_retention_policies(db, tenant_id)]


@router.post("/retention", response_model=RetentionPolicyOut, status_code=201)
async def upsert_retention(
    payload: RetentionPolicyIn,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("iam:auditor")),
    db: AsyncSession = Depends(get_db),
):
    policy = await service.upsert_retention_policy(db, tenant_id, payload)
    await db.commit()
    return service.retention_to_out(policy)


@router.get("/spc-specs", response_model=list[SpcSpecOut])
async def list_spc_specs(
    chart_id: str | None = None,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:analytics:read")),
    db: AsyncSession = Depends(get_db),
):
    return [service.spc_to_out(p) for p in await service.list_spc_specs(db, tenant_id, chart_id)]


@router.post("/spc-specs", response_model=SpcSpecOut, status_code=201)
async def create_spc_spec(
    payload: SpcSpecIn,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("spc:spec:write")),
    db: AsyncSession = Depends(get_db),
):
    spec = await service.create_spc_spec(db, tenant_id, payload)
    await service.write_audit(
        db, tenant_id, user.id, AuditAction.CREATE, "SpcSpec", spec.id, {}, payload.model_dump(),
        path="/compliance/spc-specs",
    )
    await db.commit()
    return service.spc_to_out(spec)


@router.put("/spc-specs/{spec_id}", response_model=SpcSpecOut)
async def update_spc_spec(
    spec_id: int, payload: SpcSpecIn,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("spc:spec:write")),
    db: AsyncSession = Depends(get_db),
):
    spec = await service.update_spc_spec(db, tenant_id, spec_id, payload, actor=user.id)
    await service.write_audit(
        db, tenant_id, user.id, AuditAction.UPDATE, "SpcSpec", spec.id, {}, payload.model_dump(),
        path=f"/compliance/spc-specs/{spec_id}",
    )
    await db.commit()
    return service.spc_to_out(spec)


# ----------------------------- 配置中心 -----------------------------

@router.get("/configs", response_model=list[ConfigItemOut])
async def list_configs(
    scope: str | None = None,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("platform:config:read")),
    db: AsyncSession = Depends(get_db),
):
    return [service.config_to_out(c) for c in await service.list_configs(db, tenant_id, scope)]


@router.post("/configs", response_model=ConfigItemOut, status_code=201)
async def upsert_config(
    payload: ConfigItemIn,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("platform:config:write")),
    db: AsyncSession = Depends(get_db),
):
    cfg = await service.upsert_config(db, tenant_id, payload)
    await service.write_audit(
        db, tenant_id, user.id, AuditAction.UPDATE, "ConfigItem", cfg.id, {}, payload.model_dump(),
        path="/compliance/configs",
    )
    await db.commit()
    return service.config_to_out(cfg)


@router.get("/configs/{scope}/{key}", response_model=ConfigItemOut)
async def get_config(
    scope: str, key: str,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("platform:config:read")),
    db: AsyncSession = Depends(get_db),
):
    return service.config_to_out(await service.get_config(db, tenant_id, scope, key))
