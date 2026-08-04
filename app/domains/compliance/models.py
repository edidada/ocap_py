"""BP-H 合规与审计域 ORM 模型。

支撑：GEP 合规(BP-H-01)、全链路审计追溯(BP-H-02)、电子记录（BP-H-03, 21 CFR Part 11）、
SPC 控制图规范（BP-H-04）、操作留痕不可篡改（BP-H-06）、
审计报表导出（BP-H-07）、数据保留策略（BP-H-08）。

跨域模型（租户/用户/角色/权限）已在 app.domains.iam.models 中。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import AuditAction, ConfigItemScope


class AuditLog(Base, IDMixin, TenantMixin, TimestampMixin):
    """全链路审计日志（BP-H-02/06）。"""

    __tablename__ = "audit_logs"
    user_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # AuditAction.value
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    path: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    after: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    # hash 链：sha256(prev_hash || current_record)，保证不可篡改
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class ElectronicRecord(Base, IDMixin, TenantMixin, TimestampMixin):
    """电子记录（BP-H-03, 21 CFR Part 11）。"""

    __tablename__ = "electronic_records"
    record_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # action_signoff/sop_version/spc_spec...
    reference_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    content: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    retained_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ElectronicSignature(Base, IDMixin, TenantMixin, TimestampMixin):
    """电子签名（BP-H-03, 21 CFR Part 11）。链接到电子记录。"""

    __tablename__ = "electronic_signatures"
    record_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("electronic_records.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False)
    meaning: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class RetentionPolicy(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """数据保留策略（BP-H-08）。"""

    __tablename__ = "retention_policies"
    __table_args__ = (UniqueConstraint("tenant_id", "record_type", name="uq_retention_tenant_type"),)
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    retain_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365 * 7)
    disposal_action: Mapped[str] = mapped_column(String(16), nullable=False, default="archive")  # archive/delete
    review_required: Mapped[bool] = mapped_column(default=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class SpcSpec(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """SPC 控制图规范（BP-H-04）。"""

    __tablename__ = "spc_specs"
    __table_args__ = (UniqueConstraint("tenant_id", "chart_id", "version", name="uq_spc_spec_tenant_chart"),)
    chart_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    ucl: Mapped[float] = mapped_column(nullable=False)  # Upper Control Limit
    lcl: Mapped[float] = mapped_column(nullable=False)  # Lower Control Limit
    target: Mapped[float] = mapped_column(nullable=False)
    usl: Mapped[float | None] = mapped_column(nullable=True)  # Upper Spec Limit
    lsl: Mapped[float | None] = mapped_column(nullable=True)  # Lower Spec Limit
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    comment_rules: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approved_by: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpcSpecVersion(Base, IDMixin, TimestampMixin):
    """SPC 规范历史版本快照。"""

    __tablename__ = "spc_spec_versions"
    spec_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("spc_specs.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class Notification(Base, IDMixin, TenantMixin, TimestampMixin):
    """通知（BP-I-08 迁移到 compliance/platform 共享，先在 compliance 中定义）。"""

    __tablename__ = "notifications"
    user_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="im")
    template: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfigItem(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """配置中心（BP-I-07）。"""

    __tablename__ = "config_items"
    __table_args__ = (UniqueConstraint("tenant_id", "scope", "key", name="uq_cfg_tenant_scope_key"),)
    scope: Mapped[str] = mapped_column(String(8), nullable=False, default=ConfigItemScope.TENANT.value)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    description: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(default=True)
