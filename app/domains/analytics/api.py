"""BP-G 分析与持续改进域 API。"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.analytics import service
from app.domains.analytics.schemas import (
    G2GStats,
    KpiOut,
    KpiSnapshotIn,
    KpiTrend,
    ParetoAnalysis,
    RamAnalysis,
    Report8D,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/kpis", response_model=KpiOut, status_code=201)
async def record_kpi(
    payload: KpiSnapshotIn,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:analytics:export")),
    db: AsyncSession = Depends(get_db),
) -> KpiOut:
    snap = await service.record_kpi(db, tenant_id, payload)
    await db.commit()
    return service.kpi_to_out(snap)


@router.get("/kpis", response_model=list[KpiOut])
async def list_kpis(
    kpi_code: str | None = None,
    days: int = Query(30, ge=1, le=365),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:analytics:read")),
    db: AsyncSession = Depends(get_db),
):
    start = utcnow() - timedelta(days=days)
    items = await service.list_kpis(db, tenant_id, kpi_code=kpi_code, period_from=start)
    return [service.kpi_to_out(i) for i in items]


@router.get("/kpis/trend", response_model=KpiTrend)
async def kpi_trend(
    kpi_code: str,
    days: int = Query(30, ge=1, le=365),
    period: str = "daily",
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> KpiTrend:
    return await service.get_kpi_trend(db, tenant_id, kpi_code, period=period, days=days)


@router.get("/pareto", response_model=ParetoAnalysis)
async def pareto(
    dimension: str = Query(pattern="^(equipment_id|process_step|anomaly|root_cause)$"),
    days: int = Query(30, ge=1, le=365),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ParetoAnalysis:
    now = utcnow()
    return await service.compute_pareto(
        db, tenant_id, dimension, now - timedelta(days=days), now
    )


@router.get("/g2g/stats", response_model=G2GStats)
async def g2g_stats(
    days: int = Query(30, ge=1, le=365),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> G2GStats:
    return await service.compute_g2g_stats(db, tenant_id, days=days)


@router.get("/reports/8d/{event_id}", response_model=Report8D)
async def report_8d(
    event_id: int,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> Report8D:
    return await service.generate_8d_report(db, tenant_id, event_id)


@router.get("/ram", response_model=RamAnalysis)
async def ram(
    equipment_id: str,
    days: int = Query(30, ge=1, le=365),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> RamAnalysis:
    now = utcnow()
    return await service.compute_ram(
        db, tenant_id, equipment_id, now - timedelta(days=days), now
    )
