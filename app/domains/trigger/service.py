"""BP-A 触发域服务。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page
from app.domains.trigger.dedup import compute_dedup_key
from app.domains.trigger.models import (
    EventDedupWindow,
    OcapEvent,
    TriggerRule,
    TriggerRuleVersion,
)
from app.domains.trigger.rules_engine import select_rule
from app.domains.trigger.schemas import (
    EventAdvance,
    EventCreate,
    EventIngest,
    EventOut,
    IngestResult,
    TriggerRuleCreate,
    TriggerRuleOut,
    TriggerRuleUpdate,
)
from app.utils.time import utcnow

# 合法的状态迁移
_STATUS_FLOW: dict[str, set[str]] = {
    "open": {"in_progress", "resolved", "closed"},
    "in_progress": {"resolved", "closed"},
    "resolved": {"closed"},
    "closed": set(),
    "merged": set(),
}


# ----------------------------- 事件 -----------------------------


async def create_event(db: AsyncSession, tenant_id: int, payload: EventCreate) -> OcapEvent:
    """手工创建异常事件（BP-A-06）。"""
    event = OcapEvent(
        tenant_id=tenant_id,
        source=payload.source.value,
        source_event_id=payload.source_event_id,
        severity=payload.severity.value,
        detected_at=payload.detected_at or utcnow(),
        equipment_id=payload.equipment_id,
        process_step=payload.process_step,
        parameters=payload.parameters,
        title=payload.title,
    )
    db.add(event)
    await db.flush()
    return event


async def ingest_event(db: AsyncSession, tenant_id: int, payload: EventIngest) -> IngestResult:
    """接入三方事件：规则匹配 + 去重去抖（BP-A-01~10）。"""
    detected_at = payload.detected_at or utcnow()
    data = {
        "source": payload.source.value,
        "severity": payload.severity.value,
        "equipment_id": payload.equipment_id,
        "process_step": payload.process_step,
        **payload.parameters,
    }

    rules = (
        await db.execute(
            select(TriggerRule).where(TriggerRule.tenant_id == tenant_id, TriggerRule.enabled.is_(True))
        )
    ).scalars().all()
    rule = select_rule(rules, payload.source.value, data)

    dedup_key = None
    debounce = 0
    rule_id = rule.id if rule else None
    if rule:
        dedup_key = compute_dedup_key(rule.dedup_key_tpl, data) if rule.dedup_key_tpl else None
        debounce = rule.debounce_window_s

    if dedup_key and debounce > 0:
        window = await _find_active_window(db, tenant_id, dedup_key, detected_at)
        if window is not None:
            window.count += 1
            await db.flush()
            # 合并事件：创建一条 merged 状态事件指向首次事件
            merged = OcapEvent(
                tenant_id=tenant_id,
                source=payload.source.value,
                source_event_id=payload.source_event_id,
                severity=payload.severity.value,
                detected_at=detected_at,
                equipment_id=payload.equipment_id,
                process_step=payload.process_step,
                parameters=payload.parameters,
                trigger_rule_id=rule_id,
                status="merged",
                merged_into_id=window.first_event_id,
                dedup_key=dedup_key,
                title=payload.title,
            )
            db.add(merged)
            await db.flush()
            return IngestResult(
                event_id=merged.id,
                created=False,
                merged_into=window.first_event_id,
                dedup_count=window.count,
                trigger_rule_id=rule_id,
            )

    event = OcapEvent(
        tenant_id=tenant_id,
        source=payload.source.value,
        source_event_id=payload.source_event_id,
        severity=payload.severity.value,
        detected_at=detected_at,
        equipment_id=payload.equipment_id,
        process_step=payload.process_step,
        parameters=payload.parameters,
        trigger_rule_id=rule_id,
        dedup_key=dedup_key,
        title=payload.title,
    )
    db.add(event)
    await db.flush()

    if dedup_key and debounce > 0:
        db.add(
            EventDedupWindow(
                tenant_id=tenant_id,
                rule_id=rule_id,
                dedup_key=dedup_key,
                first_event_id=event.id,
                count=1,
                window_expires_at=detected_at + timedelta(seconds=debounce),
            )
        )
        await db.flush()

    return IngestResult(event_id=event.id, created=True, dedup_count=1, trigger_rule_id=rule_id)


async def _find_active_window(
    db: AsyncSession, tenant_id: int, dedup_key: str, now
) -> EventDedupWindow | None:
    stmt = select(EventDedupWindow).where(
        EventDedupWindow.tenant_id == tenant_id,
        EventDedupWindow.dedup_key == dedup_key,
        EventDedupWindow.window_expires_at > now,
    )
    return (await db.execute(stmt)).scalars().first()


async def get_event(db: AsyncSession, tenant_id: int, event_id: int) -> OcapEvent:
    event = await db.get(OcapEvent, event_id)
    if event is None or event.tenant_id != tenant_id:
        raise NotFoundError(f"事件不存在: {event_id}")
    return event


async def list_events(
    db: AsyncSession,
    tenant_id: int,
    *,
    status: str | None = None,
    source: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[EventOut]:
    stmt = select(OcapEvent).where(OcapEvent.tenant_id == tenant_id, OcapEvent.merged_into_id.is_(None))
    if status:
        stmt = stmt.where(OcapEvent.status == status)
    if source:
        stmt = stmt.where(OcapEvent.source == source)
    total = (
        await db.execute(
            select(OcapEvent).where(
                OcapEvent.tenant_id == tenant_id, OcapEvent.merged_into_id.is_(None)
            )
        )
    ).scalars().all()
    total_count = len(total)
    stmt = stmt.order_by(OcapEvent.detected_at.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of([EventOut.model_validate(i) for i in items], total_count, page, size)


async def advance_event(
    db: AsyncSession, tenant_id: int, event_id: int, payload: EventAdvance
) -> OcapEvent:
    event = await get_event(db, tenant_id, event_id)
    new_status = payload.status.value
    allowed = _STATUS_FLOW.get(event.status, set())
    if new_status not in allowed:
        raise ConflictError(f"不允许的状态迁移: {event.status} -> {new_status}")
    event.status = new_status
    await db.flush()
    return event


# ----------------------------- 触发规则 -----------------------------


async def create_rule(db: AsyncSession, tenant_id: int, payload: TriggerRuleCreate) -> TriggerRule:
    existing = (
        await db.execute(
            select(TriggerRule).where(
                TriggerRule.tenant_id == tenant_id, TriggerRule.code == payload.code
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"规则编码已存在: {payload.code}")
    rule = TriggerRule(
        tenant_id=tenant_id,
        code=payload.code,
        name=payload.name,
        source=payload.source.value,
        condition=payload.condition,
        priority=payload.priority,
        debounce_window_s=payload.debounce_window_s,
        dedup_key_tpl=payload.dedup_key_tpl,
        enabled=payload.enabled,
        workflow_template_code=payload.workflow_template_code,
    )
    db.add(rule)
    await db.flush()
    return rule


async def list_rules(db: AsyncSession, tenant_id: int) -> list[TriggerRule]:
    stmt = select(TriggerRule).where(TriggerRule.tenant_id == tenant_id).order_by(TriggerRule.priority.desc())
    return list((await db.execute(stmt)).scalars().all())


async def get_rule(db: AsyncSession, tenant_id: int, rule_id: int) -> TriggerRule:
    rule = await db.get(TriggerRule, rule_id)
    if rule is None or rule.tenant_id != tenant_id:
        raise NotFoundError(f"规则不存在: {rule_id}")
    return rule


async def update_rule(
    db: AsyncSession, tenant_id: int, rule_id: int, payload: TriggerRuleUpdate
) -> TriggerRule:
    rule = await get_rule(db, tenant_id, rule_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(rule, k, v)
    await db.flush()
    return rule


async def publish_rule(
    db: AsyncSession, tenant_id: int, rule_id: int, published_by: int | None = None
) -> TriggerRule:
    """发布规则版本（BP-A-09 版本管理）。"""
    rule = await get_rule(db, tenant_id, rule_id)
    rule.version += 1
    snapshot = {
        "code": rule.code,
        "name": rule.name,
        "source": rule.source,
        "condition": rule.condition,
        "priority": rule.priority,
        "debounce_window_s": rule.debounce_window_s,
        "dedup_key_tpl": rule.dedup_key_tpl,
        "enabled": rule.enabled,
        "workflow_template_code": rule.workflow_template_code,
    }
    db.add(
        TriggerRuleVersion(
            rule_id=rule.id,
            version=rule.version,
            snapshot=snapshot,
            published_by=published_by,
            published_at=utcnow(),
        )
    )
    await db.flush()
    return rule


def rule_to_out(rule: TriggerRule) -> TriggerRuleOut:
    return TriggerRuleOut.model_validate(rule)
