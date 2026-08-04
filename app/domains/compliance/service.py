"""BP-H 合规与审计域 service。"""

from __future__ import annotations

import hashlib
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page, PageParams
from app.domains.action.models import ActionSignature
from app.domains.common.enums import ActionStatus, AuditAction as AuditActionEnum
from app.domains.compliance.models import (
    AuditLog,
    ConfigItem,
    ElectronicRecord,
    ElectronicSignature,
    RetentionPolicy,
    SpcSpec,
    SpcSpecVersion,
)
from app.domains.compliance.schemas import (
    ConfigItemIn,
    ConfigItemOut,
    ERecordOut,
    ESignatureOut,
    RetentionPolicyIn,
    RetentionPolicyOut,
    SpcSpecIn,
    SpcSpecOut,
)
from app.utils.time import utcnow


# ----------------------------- hash utils -----------------------------


def _canonical_audit_record(log: AuditLog) -> str:
    # 使用稳定字段（不依赖 created_at，保证 flush 前后一致）
    return (
        f"{log.tenant_id}|{log.user_id}|{log.action}|{log.resource_type}|"
        f"{log.resource_id}|{log.path}|{log.ip_address}|{log.request_id}|"
        f"{log.before!r}|{log.after!r}"
    )


# ----------------------------- 审计日志 -----------------------------


async def write_audit(
    db: AsyncSession,
    tenant_id: int,
    user_id: int | None,
    action: AuditActionEnum,
    resource_type: str,
    resource_id: int | None,
    before: dict,
    after: dict,
    path: str = "",
    ip_address: str = "",
    request_id: str | None = None,
) -> AuditLog:
    """写审计日志，带 hash 链保证不可篡改（BP-H-06）。"""
    # 读取上一条日志的 hash
    last = (await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.id.desc())
        .limit(1)
    )).scalars().first()
    prev_hash = last.record_hash if last else "GENESIS"
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action.value,
        resource_type=resource_type,
        resource_id=resource_id,
        path=path,
        ip_address=ip_address,
        request_id=request_id,
        before=before,
        after=after,
        prev_hash=prev_hash,
        record_hash="",  # 先占位
    )
    db.add(log)
    await db.flush()
    # 计算本次 hash
    raw = f"{prev_hash}|{log.id}|{_canonical_audit_record(log)}"
    log.record_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    await db.flush()
    return log


async def verify_audit_chain(db: AsyncSession, tenant_id: int, limit: int = 100) -> list[int]:
    """校验审计 hash 链，返回损坏的日志 id 列表。"""
    logs = (await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.id)
        .limit(limit)
    )).scalars().all()
    broken: list[int] = []
    prev_hash = "GENESIS"
    for log in logs:
        if log.prev_hash != prev_hash:
            broken.append(log.id)
            prev_hash = log.record_hash
            continue
        raw = f"{prev_hash}|{log.id}|{_canonical_audit_record(log)}"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if expected != log.record_hash:
            broken.append(log.id)
        prev_hash = log.record_hash
    return broken


async def list_audits(
    db: AsyncSession, tenant_id: int, params: PageParams,
    resource_type: str | None = None, action: str | None = None, user_id: int | None = None,
) -> Page[dict]:
    stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    stmt = stmt.order_by(AuditLog.created_at.desc())
    # 计数
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0
    # 分页
    stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
    rows = (await db.execute(stmt)).scalars().all()
    items = [{
        "id": r.id, "tenant_id": r.tenant_id, "user_id": r.user_id,
        "action": r.action, "resource_type": r.resource_type, "resource_id": r.resource_id,
        "path": r.path, "ip_address": r.ip_address,
        "before": r.before, "after": r.after, "created_at": r.created_at,
    } for r in rows]
    return Page.of(items, total, params.page, params.size)


# ----------------------------- 保留策略 -----------------------------


async def list_retention_policies(db: AsyncSession, tenant_id: int) -> list[RetentionPolicy]:
    return list((await db.execute(
        select(RetentionPolicy).where(RetentionPolicy.tenant_id == tenant_id)
    )).scalars().all())


async def upsert_retention_policy(
    db: AsyncSession, tenant_id: int, payload: RetentionPolicyIn
) -> RetentionPolicy:
    stmt = select(RetentionPolicy).where(
        RetentionPolicy.tenant_id == tenant_id,
        RetentionPolicy.record_type == payload.record_type,
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        existing.retain_days = payload.retain_days
        existing.disposal_action = payload.disposal_action
        existing.review_required = payload.review_required
        existing.enabled = payload.enabled
        existing.version += 1
    else:
        existing = RetentionPolicy(tenant_id=tenant_id, **payload.model_dump())
        db.add(existing)
    await db.flush()
    return existing


# ----------------------------- SPC 规范 -----------------------------


async def list_spc_specs(db: AsyncSession, tenant_id: int, chart_id: str | None = None) -> list[SpcSpec]:
    stmt = select(SpcSpec).where(SpcSpec.tenant_id == tenant_id)
    if chart_id:
        stmt = stmt.where(SpcSpec.chart_id == chart_id)
    return list((await db.execute(stmt.order_by(SpcSpec.chart_id))).scalars().all())


async def create_spc_spec(db: AsyncSession, tenant_id: int, payload: SpcSpecIn) -> SpcSpec:
    spec = SpcSpec(tenant_id=tenant_id, version=1, **payload.model_dump())
    db.add(spec)
    await db.flush()
    _snapshot_spec(db, spec)
    return spec


async def update_spc_spec(db: AsyncSession, tenant_id: int, spec_id: int, payload: SpcSpecIn, actor: int) -> SpcSpec:
    spec = await db.get(SpcSpec, spec_id)
    if spec is None or spec.tenant_id != tenant_id:
        raise NotFoundError("SPC 规范不存在")
    # 更新字段
    spec.chart_id = payload.chart_id
    spec.parameter = payload.parameter
    spec.ucl = payload.ucl
    spec.lcl = payload.lcl
    spec.target = payload.target
    spec.usl = payload.usl
    spec.lsl = payload.lsl
    spec.sample_size = payload.sample_size
    spec.comment_rules = payload.comment_rules
    spec.approved_by = actor
    spec.approved_at = utcnow()
    spec.version += 1
    await db.flush()
    _snapshot_spec(db, spec)
    return spec


def _snapshot_spec(db: AsyncSession, spec: SpcSpec) -> None:
    db.add(SpcSpecVersion(
        spec_id=spec.id, version=spec.version,
        snapshot={
            "chart_id": spec.chart_id, "parameter": spec.parameter,
            "ucl": spec.ucl, "lcl": spec.lcl, "target": spec.target,
            "usl": spec.usl, "lsl": spec.lsl, "sample_size": spec.sample_size,
            "comment_rules": spec.comment_rules,
        },
    ))


# ----------------------------- 电子记录 -----------------------------


async def create_electronic_record_from_action(
    db: AsyncSession, tenant_id: int, action_id: int, sign: ActionSignature
) -> ElectronicRecord:
    """从行动电子签名派生出电子记录（BP-H-03）。"""
    policy = (await db.execute(select(RetentionPolicy).where(
        RetentionPolicy.tenant_id == tenant_id, RetentionPolicy.record_type == "action_signoff"
    ))).scalars().first()
    retain_days = policy.retain_days if policy and policy.enabled else 365 * 7
    content = {
        "action_id": action_id, "signer_id": sign.signer_id, "meaning": sign.meaning,
        "signed_at": sign.signed_at.isoformat(), "comment": sign.comment,
    }
    content_hash = hashlib.sha256(str(content).encode("utf-8")).hexdigest()
    record = ElectronicRecord(
        tenant_id=tenant_id,
        record_type="action_signoff",
        reference_id=action_id,
        content=content,
        content_hash=content_hash,
        created_by=sign.signer_id,
        retained_until=utcnow() + timedelta(days=retain_days),
    )
    db.add(record)
    await db.flush()
    esig = ElectronicSignature(
        tenant_id=tenant_id,
        record_id=record.id,
        user_id=sign.signer_id,
        meaning=sign.meaning,
        signed_at=sign.signed_at,
        signature_hash=sign.signature_hash,
    )
    db.add(esig)
    await db.flush()
    return record


def retention_to_out(p) -> RetentionPolicyOut:
    return RetentionPolicyOut.model_validate(p)


def spc_to_out(p) -> SpcSpecOut:
    return SpcSpecOut.model_validate(p)


def erecord_to_out(p) -> ElectronicRecord:
    return ERecordOut.model_validate(p)


def esig_to_out(p) -> ElectronicSignature:
    return ESignatureOut.model_validate(p)


# ----------------------------- 配置项 -----------------------------


async def list_configs(db: AsyncSession, tenant_id: int, scope: str | None = None) -> list[ConfigItem]:
    stmt = select(ConfigItem).where(ConfigItem.tenant_id == tenant_id)
    if scope:
        stmt = stmt.where(ConfigItem.scope == scope)
    return list((await db.execute(stmt.order_by(ConfigItem.key))).scalars().all())


async def upsert_config(db: AsyncSession, tenant_id: int, payload: ConfigItemIn) -> ConfigItem:
    stmt = select(ConfigItem).where(
        ConfigItem.tenant_id == tenant_id,
        ConfigItem.scope == payload.scope.value,
        ConfigItem.key == payload.key,
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        existing.value = payload.value
        existing.description = payload.description
        existing.enabled = payload.enabled
        existing.version += 1
    else:
        existing = ConfigItem(tenant_id=tenant_id, scope=payload.scope.value, key=payload.key,
                              value=payload.value, description=payload.description, enabled=payload.enabled)
        db.add(existing)
    await db.flush()
    return existing


async def get_config(db: AsyncSession, tenant_id: int, scope: str, key: str) -> ConfigItem:
    stmt = select(ConfigItem).where(
        ConfigItem.tenant_id == tenant_id,
        ConfigItem.scope == scope,
        ConfigItem.key == key,
    )
    cfg = (await db.execute(stmt)).scalars().first()
    if cfg is None:
        raise NotFoundError("配置项不存在")
    return cfg


def config_to_out(p) -> ConfigItemOut:
    return ConfigItemOut.model_validate(p)
