"""BP-B 工作流编排域 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import WorkflowInstanceStatus, WorkflowTemplateStatus


class WorkflowTemplate(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    __tablename__ = "workflow_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "code", "version", name="uq_wf_template_code_version"),)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    process_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    anomaly_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=WorkflowTemplateStatus.DRAFT.value)
    definition: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowTemplateVersion(Base, IDMixin, TimestampMixin):
    __tablename__ = "workflow_template_versions"
    template_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("workflow_templates.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    change_log: Mapped[str] = mapped_column(String(512), nullable=False, default="")


class WorkflowInstance(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    __tablename__ = "workflow_instances"
    template_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("workflow_templates.id"), nullable=False, index=True
    )
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    current_node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WorkflowInstanceStatus.RUNNING.value, index=True
    )
    context: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_instance_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)


class WorkflowNode(Base, IDMixin, TimestampMixin):
    __tablename__ = "workflow_nodes"
    instance_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("workflow_instances.id"), nullable=False, index=True
    )
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    assignee_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    output: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class WorkflowTransitionLog(Base, IDMixin, TimestampMixin):
    __tablename__ = "workflow_transitions"
    instance_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("workflow_instances.id"), nullable=False, index=True
    )
    from_node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    guard_result: Mapped[bool | None] = mapped_column(nullable=True)
    decision_input: Mapped[str | None] = mapped_column(String(64), nullable=True)


class WorkflowIntervention(Base, IDMixin, TimestampMixin):
    __tablename__ = "workflow_interventions"
    instance_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("workflow_instances.id"), nullable=False, index=True
    )
    node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    before_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    after_status: Mapped[str | None] = mapped_column(String(16), nullable=True)


class WorkflowNodeTimeout(Base, IDMixin, TimestampMixin):
    __tablename__ = "workflow_node_timeouts"
    node_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("workflow_nodes.id"), nullable=False, index=True
    )
    instance_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    escalated: Mapped[bool] = mapped_column(default=False)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_rule: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class SopLibrary(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    __tablename__ = "sop_library"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_sop_tenant_code"),)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    steps: Mapped[list] = mapped_column(JSONBCompat, nullable=False, default=list)
