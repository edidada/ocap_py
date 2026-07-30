"""BP-E 数据集成域 ORM 模型。

支撑：E3 数据整合(BP-E-01)、SEMI 接口对接(BP-E-02)、MES/YMS/DMS/AMS/SFMM 集成(BP-E-03~07)、
开放 REST API(BP-E-08)、数据质量监控(BP-E-11)。消息队列(BP-E-09)/实时事件流(BP-E-10) P1 提供模型。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import IntegrationMode, IntegrationSystem, SyncDirection


class IntegrationConfig(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """集成配置：按系统/租户配置 mock 或 live 模式。"""

    __tablename__ = "integration_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "system", name="uq_intcfg_tenant_system"),)
    system: Mapped[str] = mapped_column(String(16), nullable=False)  # IntegrationSystem.value
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default=IntegrationMode.MOCK.value)
    endpoint: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    credentials: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    poll_interval_s: Mapped[int] = mapped_column(Integer, nullable=False, default=60)


class SyncLog(Base, IDMixin, TenantMixin, TimestampMixin):
    """集成同步日志。"""

    __tablename__ = "sync_logs"
    system: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default=SyncDirection.INBOUND.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/done/failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")


class DataQualityIssue(Base, IDMixin, TenantMixin, TimestampMixin):
    """数据质量问题（BP-E-11）。"""

    __tablename__ = "data_quality_issues"
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)  # DataQualityMetric.value
    score: Mapped[float] = mapped_column(nullable=False, default=1.0)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False)
    details: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class EventStream(Base, IDMixin, TenantMixin, TimestampMixin):
    """实时事件流接入记录（BP-E-10）。"""

    __tablename__ = "event_streams"
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    processed: Mapped[bool] = mapped_column(default=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
