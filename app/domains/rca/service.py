"""BP-C 根因分析域服务。

- CPM 上下文模式匹配：基于特征加权 Jaccard 相似度，从历史案例库推荐相似案例（BP-C-02）
- 5-Why / 鱼骨图分析工具（BP-C-04）
- 数据关联视图：聚合跨系统数据（BP-C-01）
- 重复异常识别：基于指纹（设备+工序+异常类型）的时间窗口统计（BP-C-07）
- 历史案例检索：多维度过滤（BP-C-06）
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page
from app.domains.common.enums import RcaStatus
from app.domains.rca.models import (
    CpmRun,
    RcaDataCorrelation,
    RcaFishbone,
    RcaFiveWhy,
    RcaRecord,
    RepeatDetection,
)
from app.domains.rca.schemas import (
    CpmMatch,
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
from app.utils.time import utcnow

# 重复异常识别阈值：窗口内重复次数 >= 此值判定为系统性问题
_SYSTEMIC_THRESHOLD = 3
# 重复异常识别时间窗口（秒），7 天
_REPEAT_WINDOW_S = 7 * 24 * 3600

# CPM 特征权重（可按需扩展）
_FEATURE_WEIGHTS: dict[str, int] = {
    "equipment_id": 40,
    "process_step": 25,
    "anomaly_type": 20,
    "severity": 15,
}


# ----------------------------- RCA 记录 -----------------------------


async def create_rca(db: AsyncSession, tenant_id: int, payload: RcaCreate, user_id: int) -> RcaRecord:
    rca = RcaRecord(
        tenant_id=tenant_id,
        event_id=payload.event_id,
        instance_id=payload.instance_id,
        method=payload.method.value,
        created_by=user_id,
    )
    db.add(rca)
    await db.flush()
    return rca


async def get_rca(db: AsyncSession, tenant_id: int, rca_id: int) -> RcaRecord:
    rca = await db.get(RcaRecord, rca_id)
    if rca is None or rca.tenant_id != tenant_id:
        raise NotFoundError(f"RCA 不存在: {rca_id}")
    return rca


async def list_rcas(
    db: AsyncSession,
    tenant_id: int,
    *,
    event_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[RcaOut]:
    stmt = select(RcaRecord).where(RcaRecord.tenant_id == tenant_id)
    if event_id:
        stmt = stmt.where(RcaRecord.event_id == event_id)
    if status:
        stmt = stmt.where(RcaRecord.status == status)
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(RcaRecord.id.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of([RcaOut.model_validate(i) for i in items], total, page, size)


async def update_rca(
    db: AsyncSession, tenant_id: int, rca_id: int, payload: RcaUpdate
) -> RcaRecord:
    rca = await get_rca(db, tenant_id, rca_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") == RcaStatus.CONCLUDED.value and rca.status != RcaStatus.CONCLUDED.value:
        rca.concluded_at = utcnow()
    for k, v in data.items():
        setattr(rca, k, v)
    await db.flush()
    return rca


def rca_to_out(rca: RcaRecord) -> RcaOut:
    return RcaOut.model_validate(rca)


# ----------------------------- 5-Why -----------------------------


async def add_five_why(
    db: AsyncSession, tenant_id: int, rca_id: int, payload: FiveWhyEntry
) -> RcaFiveWhy:
    await get_rca(db, tenant_id, rca_id)
    existing = (
        await db.execute(
            select(RcaFiveWhy).where(RcaFiveWhy.rca_id == rca_id, RcaFiveWhy.level == payload.level)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"层级 {payload.level} 已存在")
    entry = RcaFiveWhy(
        rca_id=rca_id,
        level=payload.level,
        question=payload.question,
        answer=payload.answer,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_five_why(db: AsyncSession, tenant_id: int, rca_id: int) -> list[RcaFiveWhy]:
    await get_rca(db, tenant_id, rca_id)
    stmt = select(RcaFiveWhy).where(RcaFiveWhy.rca_id == rca_id).order_by(RcaFiveWhy.level)
    return list((await db.execute(stmt)).scalars().all())


# ----------------------------- 鱼骨图 -----------------------------


async def add_fishbone(
    db: AsyncSession, tenant_id: int, rca_id: int, payload: FishboneEntry
) -> RcaFishbone:
    await get_rca(db, tenant_id, rca_id)
    entry = RcaFishbone(rca_id=rca_id, category=payload.category, cause=payload.cause)
    db.add(entry)
    await db.flush()
    return entry


async def list_fishbone(db: AsyncSession, tenant_id: int, rca_id: int) -> list[RcaFishbone]:
    await get_rca(db, tenant_id, rca_id)
    stmt = select(RcaFishbone).where(RcaFishbone.rca_id == rca_id).order_by(RcaFishbone.category)
    return list((await db.execute(stmt)).scalars().all())


# ----------------------------- 数据关联 -----------------------------


async def add_correlation(
    db: AsyncSession, tenant_id: int, rca_id: int, payload: DataCorrelationEntry
) -> RcaDataCorrelation:
    await get_rca(db, tenant_id, rca_id)
    entry = RcaDataCorrelation(
        rca_id=rca_id,
        source=payload.source,
        parameter=payload.parameter,
        correlation=payload.correlation,
        evidence=payload.evidence,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_correlations(db: AsyncSession, tenant_id: int, rca_id: int) -> list[RcaDataCorrelation]:
    await get_rca(db, tenant_id, rca_id)
    stmt = select(RcaDataCorrelation).where(RcaDataCorrelation.rca_id == rca_id)
    return list((await db.execute(stmt)).scalars().all())


# ----------------------------- CPM 上下文模式匹配 -----------------------------


def _score_context(query: dict, candidate: dict) -> tuple[int, list[str]]:
    """加权 Jaccard 相似度，返回 0-100 分与匹配特征列表。"""
    total_weight = 0
    matched_weight = 0
    matched: list[str] = []
    for feat, weight in _FEATURE_WEIGHTS.items():
        qv = query.get(feat)
        cv = candidate.get(feat)
        if qv is None or cv is None:
            continue
        total_weight += weight
        if qv == cv:
            matched_weight += weight
            matched.append(feat)
    if total_weight == 0:
        return 0, []
    score = round(matched_weight / total_weight * 100)
    return score, matched


async def run_cpm(
    db: AsyncSession, tenant_id: int, payload: CpmRequest, candidates: list[dict] | None = None
) -> CpmRun:
    """执行 CPM 匹配，返回匹配结果并持久化。

    candidates: 历史案例上下文列表，每项形如 {"case_id":1,"equipment_id":"EQP-01",...}。
    生产中应由 knowledge 域提供；此处允许调用方注入便于解耦。
    """
    candidates = candidates or []
    scored: list[CpmMatch] = []
    for cand in candidates:
        score, feats = _score_context(payload.context, cand)
        if score > 0:
            scored.append(CpmMatch(case_id=cand.get("case_id", 0), score=score, matched_features=feats))
    scored.sort(key=lambda m: m.score, reverse=True)
    top = scored[0].score if scored else 0
    run = CpmRun(
        tenant_id=tenant_id,
        event_id=payload.event_id,
        context=payload.context,
        matched_cases=[m.model_dump() for m in scored[:10]],
        top_score=top,
    )
    db.add(run)
    await db.flush()
    return run


async def list_cpm_runs(db: AsyncSession, tenant_id: int, event_id: int) -> list[CpmRun]:
    stmt = select(CpmRun).where(CpmRun.tenant_id == tenant_id, CpmRun.event_id == event_id)
    return list((await db.execute(stmt)).scalars().all())


def cpm_to_out(run: CpmRun) -> CpmResult:
    return CpmResult.model_validate(run)


# ----------------------------- 重复异常识别 -----------------------------


def compute_fingerprint(equipment_id: str | None, process_step: str | None, anomaly_type: str | None) -> str:
    """计算异常指纹：设备+工序+异常类型。"""
    return f"{equipment_id or '*'}|{process_step or '*'}|{anomaly_type or '*'}"


async def detect_repeat(
    db: AsyncSession,
    tenant_id: int,
    event_id: int,
    fingerprint: str,
    detected_at,
) -> RepeatResult:
    """识别重复异常。窗口内同指纹事件 >= 阈值判定为系统性（BP-C-07）。"""
    from datetime import timedelta

    window_start = detected_at - timedelta(seconds=_REPEAT_WINDOW_S)
    # 查找窗口内同指纹的历史检测记录
    stmt = select(RepeatDetection).where(
        RepeatDetection.tenant_id == tenant_id,
        RepeatDetection.fingerprint == fingerprint,
        RepeatDetection.last_seen_at >= window_start,
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing is not None:
        existing.repeat_count += 1
        existing.last_seen_at = detected_at
        existing.is_systemic = existing.repeat_count >= _SYSTEMIC_THRESHOLD
        await db.flush()
        return RepeatResult(
            event_id=event_id,
            fingerprint=fingerprint,
            repeat_count=existing.repeat_count,
            is_systemic=existing.is_systemic,
        )
    rec = RepeatDetection(
        tenant_id=tenant_id,
        event_id=event_id,
        fingerprint=fingerprint,
        repeat_count=1,
        first_seen_at=detected_at,
        last_seen_at=detected_at,
        is_systemic=False,
    )
    db.add(rec)
    await db.flush()
    return RepeatResult(
        event_id=event_id,
        fingerprint=fingerprint,
        repeat_count=1,
        is_systemic=False,
    )


# ----------------------------- 历史案例检索 -----------------------------


async def search_cases(
    db: AsyncSession,
    tenant_id: int,
    *,
    equipment_id: str | None = None,
    process_step: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[RcaOut]:
    """多维度检索历史 RCA 案例（BP-C-06）。仅在已结论的案例中检索。"""
    stmt = select(RcaRecord).where(
        RcaRecord.tenant_id == tenant_id,
        RcaRecord.status == RcaStatus.CONCLUDED.value,
    )
    # 关键词在 Python 层过滤（跨方言兼容，避免 PG-only 全文检索）
    all_items = (await db.execute(stmt)).scalars().all()
    filtered = list(all_items)
    if equipment_id:
        # equipment_id 存于事件上下文，此处简化：root_cause/conclusion 模糊匹配
        filtered = [r for r in filtered if equipment_id in (r.root_cause + r.conclusion)]
    if process_step:
        filtered = [r for r in filtered if process_step in (r.root_cause + r.conclusion)]
    if keyword:
        kw = keyword.lower()
        filtered = [r for r in filtered if kw in (r.root_cause + r.conclusion).lower()]
    total = len(filtered)
    start = (page - 1) * size
    page_items = filtered[start : start + size]
    return Page.of([RcaOut.model_validate(i) for i in page_items], total, page, size)
