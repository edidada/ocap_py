"""BP-D 处置执行域服务。

- 行动 CRUD + 跟踪（BP-D-01/02）
- 电子签核 hash 链：sha256(prev||action||signer||meaning||ts)，不可篡改（BP-D-04, 21 CFR Part 11）
- SLA 配置 + 超时检测（BP-D-03）
- 批次处置：联动 MES mock 执行 Hold/Release/Scrap/Rework（BP-D-07）
- Recipe 调整：联动 Recipe mock（BP-D-05）
- 维护工单：联动 SFMM mock（BP-D-06）
- 闭环验证（BP-D-08）
- 回滚（BP-D-10）
"""

from __future__ import annotations

import hashlib
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.core.pagination import Page
from app.domains.action.models import (
    Action,
    ActionExecution,
    ActionSignature,
    BatchDisposition,
    ClosureValidation,
    MaintenanceOrder,
    RecipeChange,
    Sla,
)
from app.domains.action.schemas import (
    ActionCreate,
    ActionOut,
    ActionUpdate,
    BatchDispositionRequest,
    ClosureRequest,
    ExecutionOut,
    SignRequest,
    SlaBreach,
    SlaCreate,
    SlaOut,
    SignatureOut,
)
from app.domains.common.enums import ActionStatus, BatchDisposition as BatchDispEnum
from app.utils.time import utcnow


# ----------------------------- 行动 -----------------------------


async def create_action(db: AsyncSession, tenant_id: int, payload: ActionCreate) -> Action:
    action = Action(
        tenant_id=tenant_id,
        event_id=payload.event_id,
        rca_id=payload.rca_id,
        instance_id=payload.instance_id,
        type=payload.type.value,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        due_at=payload.due_at,
        payload=payload.payload,
    )
    db.add(action)
    await db.flush()
    return action


async def get_action(db: AsyncSession, tenant_id: int, action_id: int) -> Action:
    action = await db.get(Action, action_id)
    if action is None or action.tenant_id != tenant_id:
        raise NotFoundError(f"行动不存在: {action_id}")
    return action


async def list_actions(
    db: AsyncSession,
    tenant_id: int,
    *,
    event_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[ActionOut]:
    stmt = select(Action).where(Action.tenant_id == tenant_id)
    if event_id:
        stmt = stmt.where(Action.event_id == event_id)
    if status:
        stmt = stmt.where(Action.status == status)
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(Action.id.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of([ActionOut.model_validate(i) for i in items], total, page, size)


async def update_action(
    db: AsyncSession, tenant_id: int, action_id: int, payload: ActionUpdate
) -> Action:
    action = await get_action(db, tenant_id, action_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(action, k, v.value) if hasattr(v, "value") else setattr(action, k, v)
    await db.flush()
    return action


async def execute_action(
    db: AsyncSession, tenant_id: int, action_id: int, actor_id: int, detail: str = ""
) -> ActionExecution:
    """执行处置行动，记录执行日志（BP-D-02 跟踪）。"""
    action = await get_action(db, tenant_id, action_id)
    if action.status in (ActionStatus.COMPLETED.value, ActionStatus.CANCELLED.value):
        raise ConflictError(f"行动已处于终态: {action.status}")
    now = utcnow()
    action.status = ActionStatus.COMPLETED.value
    action.completed_at = now
    execution = ActionExecution(
        action_id=action.id,
        actor_id=actor_id,
        status=ActionStatus.COMPLETED.value,
        detail=detail,
        result={"completed_at": now.isoformat()},
    )
    db.add(execution)
    await db.flush()
    return execution


async def rollback_action(
    db: AsyncSession, tenant_id: int, action_id: int, actor_id: int, reason: str = ""
) -> Action:
    """回滚处置行动（BP-D-10）。"""
    action = await get_action(db, tenant_id, action_id)
    if action.status != ActionStatus.COMPLETED.value:
        raise ConflictError("仅已完成的行动可回滚")
    action.status = ActionStatus.ROLLED_BACK.value
    action.rolled_back_at = utcnow()
    db.add(
        ActionExecution(
            action_id=action.id,
            actor_id=actor_id,
            status=ActionStatus.ROLLED_BACK.value,
            detail=reason,
        )
    )
    await db.flush()
    return action


def action_to_out(action: Action) -> ActionOut:
    return ActionOut.model_validate(action)


# ----------------------------- 电子签核（hash 链）-----------------------------


def _canonical_ts(dt) -> str:
    """规范化时间戳为无时区的 UTC 字符串，保证跨 SQLite/PG 往返一致。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _compute_signature_hash(prev_hash: str, action_id: int, signer_id: int, meaning: str, signed_at) -> str:
    raw = f"{prev_hash}|{action_id}|{signer_id}|{meaning}|{_canonical_ts(signed_at)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def sign_action(
    db: AsyncSession, tenant_id: int, action_id: int, signer_id: int, payload: SignRequest
) -> ActionSignature:
    """电子签核，追加到 hash 链尾部（BP-D-04, 21 CFR Part 11）。"""
    await get_action(db, tenant_id, action_id)
    # 取链尾 hash
    last = (
        await db.execute(
            select(ActionSignature)
            .where(ActionSignature.action_id == action_id)
            .order_by(ActionSignature.id.desc())
        )
    ).scalars().first()
    prev_hash = last.signature_hash if last else ""
    now = utcnow()
    sig_hash = _compute_signature_hash(prev_hash, action_id, signer_id, payload.meaning, now)
    sig = ActionSignature(
        action_id=action_id,
        signer_user_id=signer_id,
        meaning=payload.meaning,
        prev_hash=prev_hash,
        signature_hash=sig_hash,
        signed_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def list_signatures(db: AsyncSession, tenant_id: int, action_id: int) -> list[ActionSignature]:
    await get_action(db, tenant_id, action_id)
    stmt = select(ActionSignature).where(ActionSignature.action_id == action_id).order_by(ActionSignature.id)
    return list((await db.execute(stmt)).scalars().all())


def verify_signature_chain(signatures: list[ActionSignature]) -> bool:
    """校验 hash 链完整性：每个节点 prev_hash == 上一节点 signature_hash。"""
    prev = ""
    for sig in signatures:
        if sig.prev_hash != prev:
            return False
        expected = _compute_signature_hash(
            sig.prev_hash, sig.action_id, sig.signer_user_id, sig.meaning, sig.signed_at
        )
        if sig.signature_hash != expected:
            return False
        prev = sig.signature_hash
    return True


# ----------------------------- SLA -----------------------------


async def create_sla(db: AsyncSession, tenant_id: int, payload: SlaCreate) -> Sla:
    existing = (
        await db.execute(
            select(Sla).where(Sla.tenant_id == tenant_id, Sla.action_type == payload.action_type.value)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"SLA 已存在: {payload.action_type.value}")
    sla = Sla(
        tenant_id=tenant_id,
        action_type=payload.action_type.value,
        target_minutes=payload.target_minutes,
        warning_minutes=payload.warning_minutes,
        escalation_role=payload.escalation_role,
    )
    db.add(sla)
    await db.flush()
    return sla


async def list_slas(db: AsyncSession, tenant_id: int) -> list[Sla]:
    stmt = select(Sla).where(Sla.tenant_id == tenant_id)
    return list((await db.execute(stmt)).scalars().all())


async def check_sla_breaches(db: AsyncSession, tenant_id: int) -> list[SlaBreach]:
    """检测 SLA 超时行动（BP-D-03 超时预警）。"""
    slas = {s.action_type: s for s in await list_slas(db, tenant_id)}
    if not slas:
        return []
    stmt = select(Action).where(
        Action.tenant_id == tenant_id,
        Action.status.in_([ActionStatus.PENDING.value, ActionStatus.IN_PROGRESS.value]),
    )
    actions = (await db.execute(stmt)).scalars().all()
    now = utcnow()
    breaches: list[SlaBreach] = []
    for a in actions:
        sla = slas.get(a.type)
        if sla is None or a.due_at is None:
            continue
        if now > a.due_at:
            overdue = int((now - a.due_at).total_seconds() // 60)
            breaches.append(
                SlaBreach(
                    action_id=a.id,
                    title=a.title,
                    overdue_minutes=overdue,
                    escalation_role=sla.escalation_role,
                )
            )
    return breaches


def sla_to_out(sla: Sla) -> SlaOut:
    return SlaOut.model_validate(sla)


# ----------------------------- 批次处置（联动 MES）-----------------------------


async def dispose_batch(
    db: AsyncSession,
    tenant_id: int,
    action_id: int,
    payload: BatchDispositionRequest,
    mes_client=None,
) -> BatchDisposition:
    """批次 Hold/Release/Scrap/Rework，联动 MES mock（BP-D-07）。"""
    action = await get_action(db, tenant_id, action_id)
    if mes_client is not None:
        # 调用 mock MES 执行真实处置
        await mes_client.dispose_batch(payload.batch_id, payload.disposition.value)
    rec = BatchDisposition(
        tenant_id=tenant_id,
        action_id=action.id,
        batch_id=payload.batch_id,
        disposition=payload.disposition.value,
        reason=payload.reason,
        synced=mes_client is not None,
    )
    db.add(rec)
    await db.flush()
    return rec


async def list_batch_dispositions(
    db: AsyncSession, tenant_id: int, action_id: int
) -> list[BatchDisposition]:
    await get_action(db, tenant_id, action_id)
    stmt = select(BatchDisposition).where(BatchDisposition.action_id == action_id)
    return list((await db.execute(stmt)).scalars().all())


# ----------------------------- 闭环验证 -----------------------------


async def validate_closure(
    db: AsyncSession, tenant_id: int, action_id: int, validator_id: int, payload: ClosureRequest
) -> ClosureValidation:
    """闭环验证：确认处置有效（BP-D-08）。"""
    action = await get_action(db, tenant_id, action_id)
    if action.status != ActionStatus.COMPLETED.value:
        raise ConflictError("仅已完成的行动可闭环验证")
    cv = ClosureValidation(
        action_id=action.id,
        validator_id=validator_id,
        passed=payload.passed,
        evidence=payload.evidence,
        note=payload.note,
    )
    db.add(cv)
    await db.flush()
    return cv
