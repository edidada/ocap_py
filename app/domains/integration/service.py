"""BP-E 数据集成域服务。

- 集成配置 CRUD（BP-E-01/02）：mock/live 模式切换
- 同步触发 + 日志（BP-E-03~07）：调用 IntegrationRegistry 执行拉取，记录日志
- 健康检查（BP-E-08）：批量探测三方系统
- 数据质量监控（BP-E-11）：完整性/及时性/一致性/有效性评分
- 事件流接入（BP-E-10）：异步落库 + 标记处理
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page
from app.domains.common.enums import SyncDirection
from app.domains.integration.models import (
    DataQualityIssue,
    EventStream,
    IntegrationConfig,
    SyncLog,
)
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
from app.utils.time import utcnow


# ----------------------------- 配置 -----------------------------


async def create_config(
    db: AsyncSession, tenant_id: int, payload: IntegrationConfigCreate
) -> IntegrationConfig:
    existing = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.tenant_id == tenant_id,
                IntegrationConfig.system == payload.system.value,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"集成配置已存在: {payload.system.value}")
    cfg = IntegrationConfig(
        tenant_id=tenant_id,
        system=payload.system.value,
        mode=payload.mode.value,
        endpoint=payload.endpoint,
        credentials=payload.credentials,
        enabled=payload.enabled,
        poll_interval_s=payload.poll_interval_s,
    )
    db.add(cfg)
    await db.flush()
    return cfg


async def get_config(db: AsyncSession, tenant_id: int, config_id: int) -> IntegrationConfig:
    cfg = await db.get(IntegrationConfig, config_id)
    if cfg is None or cfg.tenant_id != tenant_id:
        raise NotFoundError(f"集成配置不存在: {config_id}")
    return cfg


async def list_configs(db: AsyncSession, tenant_id: int) -> list[IntegrationConfig]:
    stmt = select(IntegrationConfig).where(IntegrationConfig.tenant_id == tenant_id).order_by(
        IntegrationConfig.system
    )
    return list((await db.execute(stmt)).scalars().all())


async def update_config(
    db: AsyncSession, tenant_id: int, config_id: int, payload: IntegrationConfigUpdate
) -> IntegrationConfig:
    cfg = await get_config(db, tenant_id, config_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cfg, k, v.value if hasattr(v, "value") else v)
    await db.flush()
    return cfg


def config_to_out(cfg: IntegrationConfig) -> IntegrationConfigOut:
    return IntegrationConfigOut.model_validate(cfg)


# ----------------------------- 同步 -----------------------------


async def trigger_sync(
    db: AsyncSession, tenant_id: int, system: str, registry=None
) -> SyncResult:
    """触发指定系统的数据同步，记录日志。"""
    now = utcnow()
    log = SyncLog(
        tenant_id=tenant_id,
        system=system,
        direction=SyncDirection.INBOUND.value,
        status="running",
        started_at=now,
    )
    db.add(log)
    await db.flush()

    records = 0
    error = ""
    try:
        if registry is not None:
            client = registry.get(system)
            # 拉取数据：按系统调用对应方法，统计记录数
            records = await _pull_records(client, system)
        log.status = "done"
    except Exception as e:  # noqa: BLE001
        log.status = "failed"
        error = str(e)
    log.completed_at = utcnow()
    log.records_count = records
    log.error = error
    await db.flush()
    return SyncResult(
        log_id=log.id, system=system, status=log.status, records_count=records, error=error
    )


async def _pull_records(client, system: str) -> int:
    """按系统拉取数据并返回记录数。"""
    if system == "spc":
        events = client.store.spc_events if hasattr(client, "store") else []
        return len(events)
    if system == "mes":
        batches = await client.list_batches() if hasattr(client, "list_batches") else []
        return len(batches)
    # 通用：从 store 统计
    if hasattr(client, "store"):
        store = client.store
        return sum(
            len(getattr(store, attr))
            for attr in ["batches", "recipes", "spc_charts", "fdc_alarms", "ams_alarms"]
        )
    return 0


async def list_sync_logs(
    db: AsyncSession, tenant_id: int, system: str | None = None, page: int = 1, size: int = 20
) -> Page[SyncLogOut]:
    stmt = select(SyncLog).where(SyncLog.tenant_id == tenant_id)
    if system:
        stmt = stmt.where(SyncLog.system == system)
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(SyncLog.started_at.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of([SyncLogOut.model_validate(i) for i in items], total, page, size)


# ----------------------------- 健康检查 -----------------------------


async def health_check_all(registry) -> list[HealthResult]:
    """批量探测所有支持的集成系统健康状态（BP-E-08）。"""
    results: list[HealthResult] = []
    for system in registry.supported_systems():
        client = registry.get(system)
        dto = await client.health()
        results.append(HealthResult(system=system, status=dto.status, latency_ms=dto.latency_ms))
    return results


# ----------------------------- 数据质量 -----------------------------


async def record_quality_issue(
    db: AsyncSession,
    tenant_id: int,
    source: str,
    metric: str,
    score: float,
    details: dict | None = None,
) -> DataQualityIssue:
    issue = DataQualityIssue(
        tenant_id=tenant_id,
        source=source,
        metric=metric,
        score=score,
        detected_at=utcnow(),
        details=details or {},
    )
    db.add(issue)
    await db.flush()
    return issue


async def list_quality_issues(
    db: AsyncSession, tenant_id: int, resolved: bool | None = None
) -> list[DataQualityIssue]:
    stmt = select(DataQualityIssue).where(DataQualityIssue.tenant_id == tenant_id)
    if resolved is not None:
        stmt = stmt.where(DataQualityIssue.resolved == resolved)
    return list((await db.execute(stmt)).scalars().all())


# ----------------------------- 事件流 -----------------------------


async def ingest_event_stream(
    db: AsyncSession, tenant_id: int, payload: EventStreamIngest
) -> EventStream:
    """接入实时事件流（BP-E-10）。"""
    stream = EventStream(
        tenant_id=tenant_id,
        source=payload.source.value,
        event_type=payload.event_type,
        payload=payload.payload,
    )
    db.add(stream)
    await db.flush()
    return stream


async def list_event_streams(
    db: AsyncSession, tenant_id: int, processed: bool | None = None, page: int = 1, size: int = 20
) -> Page[EventStream]:
    stmt = select(EventStream).where(EventStream.tenant_id == tenant_id)
    if processed is not None:
        stmt = stmt.where(EventStream.processed == processed)
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(EventStream.id.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of(items, total, page, size)  # type: ignore[arg-type]
