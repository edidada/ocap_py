"""BP-D 处置执行域 ORM 模型。

支撑：行动计划(BP-D-01)、行动跟踪(BP-D-02)、SLA(BP-D-03)、
电子签核 hash 链(BP-D-04, 21 CFR Part 11)、Recipe 联动(BP-D-05)、
维护联动(BP-D-06)、批次 Hold/Release(BP-D-07)、闭环验证(BP-D-08)、
回滚(BP-D-10)。脚本执行(BP-D-09) P2 占位。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import ActionStatus, ActionType


class Action(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """处置行动项。"""

    __tablename__ = "actions"
    event_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    rca_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    instance_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # ActionType.value
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assignee_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ActionStatus.PENDING.value, index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class ActionExecution(Base, IDMixin, TimestampMixin):
    """行动执行记录（每次执行/重试一条）。"""

    __tablename__ = "action_executions"
    action_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("actions.id"), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class ActionSignature(Base, IDMixin, TimestampMixin):
    """电子签核（hash 链，21 CFR Part 11 不可篡改）。

    hash = sha256(prev_hash || action_id || signer_id || meaning || signed_at)
    """

    __tablename__ = "action_signatures"
    action_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("actions.id"), nullable=False, index=True)
    signer_user_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False)
    meaning: Mapped[str] = mapped_column(String(128), nullable=False, default="approve")
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Sla(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """SLA 配置。"""

    __tablename__ = "slas"
    __table_args__ = (UniqueConstraint("tenant_id", "action_type", name="uq_sla_tenant_type"),)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalation_role: Mapped[str | None] = mapped_column(String(32), nullable=True)


class BatchDisposition(Base, IDMixin, TenantMixin, TimestampMixin):
    """批次处置记录（Hold/Release/Scrap/Rework，BP-D-07）。"""

    __tablename__ = "batch_dispositions"
    action_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("actions.id"), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    disposition: Mapped[str] = mapped_column(String(16), nullable=False)  # BatchDisposition.value
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    synced: Mapped[bool] = mapped_column(default=False)


class RecipeChange(Base, IDMixin, TenantMixin, TimestampMixin):
    """配方调整记录（BP-D-05）。"""

    __tablename__ = "recipe_changes"
    action_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("actions.id"), nullable=False, index=True)
    recipe_id: Mapped[str] = mapped_column(String(64), nullable=False)
    old_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    new_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    params: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    synced: Mapped[bool] = mapped_column(default=False)


class MaintenanceOrder(Base, IDMixin, TenantMixin, TimestampMixin):
    """设备维护工单（BP-D-06）。"""

    __tablename__ = "maintenance_orders"
    action_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("actions.id"), nullable=False, index=True)
    equipment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False, default="corrective")
    external_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")


class ClosureValidation(Base, IDMixin, TimestampMixin):
    """闭环验证记录（BP-D-08）。"""

    __tablename__ = "closure_validations"
    action_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("actions.id"), nullable=False, index=True)
    validator_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    passed: Mapped[bool] = mapped_column(nullable=False, default=False)
    evidence: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(String(512), nullable=False, default="")


class ActionScript(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """处置脚本（BP-D-09，P2 占位）。"""

    __tablename__ = "action_scripts"
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(default=True)
