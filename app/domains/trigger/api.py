"""BP-A 触发域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.trigger import service
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

router = APIRouter(prefix="/triggers", tags=["triggers"])


# ----------------------------- 事件 -----------------------------


@router.post("/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:event:create")),
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    event = await service.create_event(db, tenant_id, payload)
    await db.commit()
    return EventOut.model_validate(event)


@router.post("/events/ingest", response_model=IngestResult)
async def ingest_event(
    payload: EventIngest,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:event:create")),
    db: AsyncSession = Depends(get_db),
) -> IngestResult:
    result = await service.ingest_event(db, tenant_id, payload)
    await db.commit()
    return result


@router.get("/events", response_model=list[EventOut])
async def list_events(
    status: str | None = None,
    source: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:event:read")),
    db: AsyncSession = Depends(get_db),
):
    page_result = await service.list_events(db, tenant_id, status=status, source=source, page=page, size=size)
    return page_result.items


@router.get("/events/{event_id}", response_model=EventOut)
async def get_event(
    event_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:event:read")),
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    event = await service.get_event(db, tenant_id, event_id)
    return EventOut.model_validate(event)


@router.post("/events/{event_id}/advance", response_model=EventOut)
async def advance_event(
    event_id: int,
    payload: EventAdvance,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:event:advance")),
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    event = await service.advance_event(db, tenant_id, event_id, payload)
    await db.commit()
    return EventOut.model_validate(event)


# ----------------------------- 触发规则 -----------------------------


@router.post("/rules", response_model=TriggerRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: TriggerRuleCreate,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:config:write")),
    db: AsyncSession = Depends(get_db),
) -> TriggerRuleOut:
    rule = await service.create_rule(db, tenant_id, payload)
    await db.commit()
    return service.rule_to_out(rule)


@router.get("/rules", response_model=list[TriggerRuleOut])
async def list_rules(
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rules = await service.list_rules(db, tenant_id)
    return [service.rule_to_out(r) for r in rules]


@router.get("/rules/{rule_id}", response_model=TriggerRuleOut)
async def get_rule(
    rule_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TriggerRuleOut:
    rule = await service.get_rule(db, tenant_id, rule_id)
    return service.rule_to_out(rule)


@router.patch("/rules/{rule_id}", response_model=TriggerRuleOut)
async def update_rule(
    rule_id: int,
    payload: TriggerRuleUpdate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:config:write")),
    db: AsyncSession = Depends(get_db),
) -> TriggerRuleOut:
    rule = await service.update_rule(db, tenant_id, rule_id, payload)
    await db.commit()
    return service.rule_to_out(rule)


@router.post("/rules/{rule_id}/publish", response_model=TriggerRuleOut)
async def publish_rule(
    rule_id: int,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:config:write")),
    db: AsyncSession = Depends(get_db),
) -> TriggerRuleOut:
    rule = await service.publish_rule(db, tenant_id, rule_id, published_by=user.id)
    await db.commit()
    return service.rule_to_out(rule)
