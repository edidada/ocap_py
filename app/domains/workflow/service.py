"""BP-B 工作流编排域服务。

将内嵌 BPMN-lite 引擎（workflow_engine）与持久化层桥接：
- 模板管理 + 版本发布（BP-B-01/06）
- 实例启动 + 节点推进 + 人工干预（BP-B-02/03/04/07）
- SOP 标准操作步骤库（BP-B-05）
- 流程实例审计（BP-B-09）：transition 日志 + intervention 记录
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.core.pagination import Page
from app.domains.common.enums import (
    InterventionType,
    WorkflowInstanceStatus,
    WorkflowTemplateStatus,
)
from app.domains.workflow.models import (
    SopLibrary,
    WorkflowInstance,
    WorkflowIntervention,
    WorkflowNode,
    WorkflowTemplate,
    WorkflowTemplateVersion,
    WorkflowTransitionLog,
)
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
from app.utils.time import utcnow
from app.workflow_engine.compiler import compile_template, validate_template
from app.workflow_engine.engine import StateMachine
from app.workflow_engine.types import Context, NodeStatus

# 节点状态行 -> WorkflowNode.status 映射
_NODE_ACTIVE = "active"
_NODE_DONE = "completed"
_NODE_SKIPPED = "skipped"


# ----------------------------- 模板 -----------------------------


async def create_template(db: AsyncSession, tenant_id: int, payload: TemplateCreate) -> WorkflowTemplate:
    """创建工作流模板（草稿态，BP-B-01）。"""
    errors = validate_template(payload.definition)
    if errors:
        raise ValidationFailed("模板定义校验失败", details=errors)
    existing = (
        await db.execute(
            select(WorkflowTemplate).where(
                WorkflowTemplate.tenant_id == tenant_id,
                WorkflowTemplate.code == payload.code,
                WorkflowTemplate.status != WorkflowTemplateStatus.ARCHIVED.value,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"模板编码已存在: {payload.code}")
    tpl = WorkflowTemplate(
        tenant_id=tenant_id,
        code=payload.code,
        name=payload.name,
        process_step=payload.process_step,
        anomaly_type=payload.anomaly_type,
        definition=payload.definition,
        status=WorkflowTemplateStatus.DRAFT.value,
    )
    db.add(tpl)
    await db.flush()
    return tpl


async def get_template(db: AsyncSession, tenant_id: int, template_id: int) -> WorkflowTemplate:
    tpl = await db.get(WorkflowTemplate, template_id)
    if tpl is None or tpl.tenant_id != tenant_id:
        raise NotFoundError(f"模板不存在: {template_id}")
    return tpl


async def list_templates(
    db: AsyncSession,
    tenant_id: int,
    *,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[TemplateOut]:
    stmt = select(WorkflowTemplate).where(WorkflowTemplate.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(WorkflowTemplate.status == status)
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(WorkflowTemplate.id.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of([TemplateOut.model_validate(i) for i in items], total, page, size)


async def update_template(
    db: AsyncSession, tenant_id: int, template_id: int, payload: TemplateUpdate
) -> WorkflowTemplate:
    tpl = await get_template(db, tenant_id, template_id)
    if tpl.status == WorkflowTemplateStatus.PUBLISHED.value:
        raise ConflictError("已发布模板不可修改，请创建新版本")
    data = payload.model_dump(exclude_unset=True)
    if "definition" in data and data["definition"] != tpl.definition:
        errors = validate_template(data["definition"])
        if errors:
            raise ValidationFailed("模板定义校验失败", details=errors)
    for k, v in data.items():
        setattr(tpl, k, v)
    await db.flush()
    return tpl


async def publish_template(
    db: AsyncSession, tenant_id: int, template_id: int, published_by: int | None = None
) -> WorkflowTemplate:
    """发布模板版本（BP-B-06 版本管理）。"""
    tpl = await get_template(db, tenant_id, template_id)
    errors = validate_template(tpl.definition)
    if errors:
        raise ValidationFailed("模板定义校验失败", details=errors)
    tpl.version += 1
    tpl.status = WorkflowTemplateStatus.PUBLISHED.value
    tpl.published_at = utcnow()
    db.add(
        WorkflowTemplateVersion(
            template_id=tpl.id,
            version=tpl.version,
            definition=tpl.definition,
            change_log=f"published by user {published_by}",
        )
    )
    await db.flush()
    return tpl


def template_to_out(tpl: WorkflowTemplate) -> TemplateOut:
    return TemplateOut.model_validate(tpl)


# ----------------------------- 实例 -----------------------------


async def start_instance(
    db: AsyncSession, tenant_id: int, payload: StartInstance
) -> WorkflowInstance:
    """启动工作流实例（BP-B-02 引导式排查）。"""
    tpl = await get_template(db, tenant_id, payload.template_id)
    if tpl.status != WorkflowTemplateStatus.PUBLISHED.value:
        raise ConflictError("仅已发布模板可启动实例")
    sm = compile_template(tpl.definition)
    ctx = Context(
        tenant_id=tenant_id,
        event={"event_id": payload.event_id} if payload.event_id else {},
        variables=dict(payload.variables),
    )
    activated = sm.start(ctx)
    now = utcnow()
    inst = WorkflowInstance(
        tenant_id=tenant_id,
        template_id=tpl.id,
        template_version=tpl.version,
        event_id=payload.event_id,
        current_node_key=activated[0] if activated else None,
        status=WorkflowInstanceStatus.RUNNING.value,
        context=ctx.to_snapshot(),
        started_at=now,
    )
    db.add(inst)
    await db.flush()
    await _persist_nodes(db, inst.id, sm, ctx, now)
    await _log_transition(db, inst.id, None, activated[0] if activated else None, now)
    return inst


async def get_instance(db: AsyncSession, tenant_id: int, instance_id: int) -> WorkflowInstance:
    inst = await db.get(WorkflowInstance, instance_id)
    if inst is None or inst.tenant_id != tenant_id:
        raise NotFoundError(f"工作流实例不存在: {instance_id}")
    return inst


async def list_instances(
    db: AsyncSession,
    tenant_id: int,
    *,
    status: str | None = None,
    event_id: int | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[InstanceOut]:
    stmt = select(WorkflowInstance).where(WorkflowInstance.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(WorkflowInstance.status == status)
    if event_id:
        stmt = stmt.where(WorkflowInstance.event_id == event_id)
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(WorkflowInstance.started_at.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return Page.of([InstanceOut.model_validate(i) for i in items], total, page, size)


async def list_nodes(db: AsyncSession, tenant_id: int, instance_id: int) -> list[WorkflowNode]:
    inst = await get_instance(db, tenant_id, instance_id)
    stmt = select(WorkflowNode).where(WorkflowNode.instance_id == inst.id).order_by(WorkflowNode.id)
    return list((await db.execute(stmt)).scalars().all())


async def advance_instance(
    db: AsyncSession, tenant_id: int, instance_id: int, payload: AdvanceRequest
) -> AdvanceResult:
    """推进工作流实例节点（BP-B-03 动态决策树 / BP-B-04 串并行）。"""
    inst = await get_instance(db, tenant_id, instance_id)
    if inst.status != WorkflowInstanceStatus.RUNNING.value:
        raise ConflictError(f"实例非运行态，无法推进: {inst.status}")
    tpl = await get_template(db, tenant_id, inst.template_id)
    sm = compile_template(tpl.definition)
    ctx = Context.from_snapshot(inst.context, instance_id=inst.id)

    before_active = set(ctx.active_nodes())
    if payload.action == "complete_task":
        activated = sm.complete_task(ctx, payload.node_key, payload.output)
    elif payload.action == "take_decision":
        if not payload.choice:
            raise ValidationFailed("take_decision 需要 choice")
        activated = sm.take_decision(ctx, payload.node_key, payload.choice)
    elif payload.action == "skip":
        sm.skip_task(ctx, payload.node_key, payload.reason)
        activated = sm._evaluate_outgoing(payload.node_key, ctx)
    elif payload.action == "jump":
        if not payload.target_node_key:
            raise ValidationFailed("jump 需要 target_node_key")
        activated = sm.jump_to(ctx, payload.target_node_key)
    else:  # pragma: no cover - 受 schema 约束
        raise ValidationFailed(f"未知动作: {payload.action}")

    terminal = sm.is_terminal(ctx)
    now = utcnow()
    inst.context = ctx.to_snapshot()
    flag_modified(inst, "context")
    inst.version += 1
    inst.current_node_key = activated[0] if activated else None
    if terminal:
        inst.status = WorkflowInstanceStatus.COMPLETED.value
        inst.completed_at = now

    await _persist_nodes(db, inst.id, sm, ctx, now)
    # 记录流转日志
    for new_key in activated:
        if new_key not in before_active:
            await _log_transition(
                db, inst.id, payload.node_key, new_key, now, payload.choice
            )
    await db.flush()
    return AdvanceResult(
        instance=InstanceOut.model_validate(inst),
        activated_nodes=activated,
        terminal=terminal,
    )


async def intervene(
    db: AsyncSession, tenant_id: int, instance_id: int, payload: InterveneRequest, actor_user_id: int
) -> WorkflowInstance:
    """人工干预与例外处理（BP-B-07）。"""
    inst = await get_instance(db, tenant_id, instance_id)
    if inst.status != WorkflowInstanceStatus.RUNNING.value:
        raise ConflictError(f"实例非运行态，无法干预: {inst.status}")
    before = inst.status
    if payload.type == InterventionType.ESCALATION.value:
        inst.status = WorkflowInstanceStatus.SUSPENDED.value
    elif payload.type == InterventionType.REASSIGN.value:
        # 重新指派：仅记录，不改状态机
        pass
    else:
        # skip/jump/override 走 advance 通道
        advance_payload = AdvanceRequest(
            action="skip" if payload.type == InterventionType.SKIP.value else "jump",
            node_key=payload.node_key or "",
            target_node_key=payload.target_node_key,
            reason=payload.reason,
        )
        await advance_instance(db, tenant_id, instance_id, advance_payload)
        inst = await get_instance(db, tenant_id, instance_id)
    db.add(
        WorkflowIntervention(
            instance_id=inst.id,
            node_key=payload.node_key,
            type=payload.type,
            actor_user_id=actor_user_id,
            reason=payload.reason,
            before_status=before,
            after_status=inst.status,
        )
    )
    await db.flush()
    return inst


# ----------------------------- SOP -----------------------------


async def create_sop(db: AsyncSession, tenant_id: int, payload: SopCreate) -> SopLibrary:
    existing = (
        await db.execute(
            select(SopLibrary).where(SopLibrary.tenant_id == tenant_id, SopLibrary.code == payload.code)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"SOP 编码已存在: {payload.code}")
    sop = SopLibrary(
        tenant_id=tenant_id,
        code=payload.code,
        title=payload.title,
        steps=payload.steps,
    )
    db.add(sop)
    await db.flush()
    return sop


async def list_sops(db: AsyncSession, tenant_id: int) -> list[SopLibrary]:
    stmt = select(SopLibrary).where(SopLibrary.tenant_id == tenant_id).order_by(SopLibrary.code)
    return list((await db.execute(stmt)).scalars().all())


async def get_sop(db: AsyncSession, tenant_id: int, sop_id: int) -> SopLibrary:
    sop = await db.get(SopLibrary, sop_id)
    if sop is None or sop.tenant_id != tenant_id:
        raise NotFoundError(f"SOP 不存在: {sop_id}")
    return sop


def sop_to_out(sop: SopLibrary) -> SopOut:
    return SopOut.model_validate(sop)


# ----------------------------- 内部持久化 -----------------------------


async def _persist_nodes(
    db: AsyncSession, instance_id: int, sm: StateMachine, ctx: Context, now
) -> None:
    """同步 workflow_nodes 行与引擎 ctx.statuses。"""
    existing = {
        n.node_key: n
        for n in (
            await db.execute(select(WorkflowNode).where(WorkflowNode.instance_id == instance_id))
        ).scalars().all()
    }
    for key, node in sm.nodes.items():
        status = ctx.statuses.get(key, NodeStatus.PENDING.value)
        row = existing.get(key)
        if row is None:
            row = WorkflowNode(
                instance_id=instance_id,
                node_key=key,
                node_type=node.type.value,
                status=NodeStatus.PENDING.value,
                assignee_role=node.assignee_role,
            )
            db.add(row)
            existing[key] = row
        # 状态映射
        if status == NodeStatus.ACTIVE.value:
            row.status = _NODE_ACTIVE
            if row.started_at is None:
                row.started_at = now
        elif status == NodeStatus.COMPLETED.value:
            row.status = _NODE_DONE
            if row.started_at is None:
                row.started_at = now
            if row.completed_at is None:
                row.completed_at = now
        elif status == NodeStatus.SKIPPED.value:
            row.status = _NODE_SKIPPED
        # 输出
        outputs = ctx.variables.get("outputs", {})
        if key in outputs:
            row.output = outputs[key]
            flag_modified(row, "output")
        # 超时
        if node.timeout_s and row.status == _NODE_ACTIVE and row.due_at is None:
            row.due_at = now + timedelta(seconds=node.timeout_s)
    await db.flush()


async def _log_transition(
    db: AsyncSession,
    instance_id: int,
    from_key: str | None,
    to_key: str | None,
    taken_at,
    decision_input: str | None = None,
) -> None:
    db.add(
        WorkflowTransitionLog(
            instance_id=instance_id,
            from_node_key=from_key,
            to_node_key=to_key,
            taken_at=taken_at,
            decision_input=decision_input,
        )
    )
