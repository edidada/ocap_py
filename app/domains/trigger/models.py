"""BP-A 异常感知与触发域 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import EventSource, EventStatus, Severity


class TriggerRule(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    __tablename__ = "trigger_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_trigger_rule_tenant_code"),)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # EventSource.value
    condition: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    debounce_window_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dedup_key_tpl: Mapped[str | None] = mapped_column(String(256), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    workflow_template_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TriggerRuleVersion(Base, IDMixin, TimestampMixin):
    __tablename__ = "trigger_rule_versions"
    rule_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("trigger_rules.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    published_by: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OcapEvent(Base, IDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "ocap_events"
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # EventSource.value
    source_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default=Severity.WARNING.value)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    equipment_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    process_step: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    parameters: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    trigger_rule_id: Mapped[int | None] = mapped_column(
        BigIntVariant(), ForeignKey("trigger_rules.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=EventStatus.OPEN.value, index=True)
    merged_into_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    dedup_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")


class EventDedupWindow(Base, IDMixin, TimestampMixin):
    __tablename__ = "event_dedup_windows"
    tenant_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    first_event_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("ocap_events.id"), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    window_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
