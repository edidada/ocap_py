"""BP-E 数据集成域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.integration import service
from app.domains.integration.schemas import (
    DataQualityIssueOut,
    EventStreamIngest,
    HealthResult,
    IntegrationConfigCreate,
    IntegrationConfigOut,
    IntegrationConfigUpdate,
    SyncLogOut,
    SyncResult,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/configs", response_model=IntegrationConfigOut, status_code=status.HTTP_201_CREATED)
async def create_config(
    payload: IntegrationConfigCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:integration:configure")),
    db: AsyncSession = Depends(get_db),
) -> IntegrationConfigOut:
    cfg = await service.create_config(db, tenant_id, payload)
    await db.commit()
    return service.config_to_out(cfg)


@router.get("/configs", response_model=list[IntegrationConfigOut])
async def list_configs(
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfgs = await service.list_configs(db, tenant_id)
    return [service.config_to_out(c) for c in cfgs]


@router.patch("/configs/{config_id}", response_model=IntegrationConfigOut)
async def update_config(
    config_id: int,
    payload: IntegrationConfigUpdate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:integration:configure")),
    db: AsyncSession = Depends(get_db),
) -> IntegrationConfigOut:
    cfg = await service.update_config(db, tenant_id, config_id, payload)
    await db.commit()
    return service.config_to_out(cfg)


@router.post("/sync/{system}", response_model=SyncResult)
async def trigger_sync(
    system: str,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:integration:sync")),
    db: AsyncSession = Depends(get_db),
) -> SyncResult:
    from app.integrations.registry import get_integration_registry

    reg = get_integration_registry()
    result = await service.trigger_sync(db, tenant_id, system, reg)
    await db.commit()
    return result


@router.get("/sync/logs", response_model=list[SyncLogOut])
async def list_sync_logs(
    system: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_sync_logs(db, tenant_id, system=system, page=page, size=size)
    return result.items


@router.get("/health", response_model=list[HealthResult])
async def health_check(
    _: User = Depends(get_current_user),
):
    from app.integrations.registry import get_integration_registry

    reg = get_integration_registry()
    return await service.health_check_all(reg)


@router.get("/quality-issues", response_model=list[DataQualityIssueOut])
async def list_quality_issues(
    resolved: bool | None = None,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issues = await service.list_quality_issues(db, tenant_id, resolved=resolved)
    return [DataQualityIssueOut.model_validate(i) for i in issues]


@router.post("/event-streams", status_code=status.HTTP_201_CREATED)
async def ingest_event_stream(
    payload: EventStreamIngest,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:integration:sync")),
    db: AsyncSession = Depends(get_db),
):
    stream = await service.ingest_event_stream(db, tenant_id, payload)
    await db.commit()
    return {"id": stream.id, "source": stream.source, "processed": stream.processed}
