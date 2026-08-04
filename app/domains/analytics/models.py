"""BP-G 分析与持续改进域 ORM 模型。

支撑：KPI 看板(BP-G-01)、趋势分析(BP-G-02)、Pareto(BP-G-03)、
G2G 周期(BP-G-04)、人为错误率(BP-G-05)、设备 RAM(BP-G-06)、
8D 报告(BP-G-07)、预测分析(BP-G-08, P2)。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import KpiCode, Period


class KpiSnapshot(Base, IDMixin, TenantMixin, TimestampMixin):
    """KPI 快照（BP-G-01/05/06）。"""

    __tablename__ = "kpi_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "kpi_code", "period", "snapshot_at", name="uq_kpi_tenant_period"),)
    kpi_code: Mapped[str] = mapped_column(String(32), nullable=False)  # KpiCode.value
    period: Mapped[str] = mapped_column(String(16), nullable=False, default=Period.DAILY.value)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target: Mapped[float] = mapped_column(Float, nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    group_by: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 分组维度：equipment_id/process_step


class AnalyticsReport(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """分析报表（BP-G-02/03）。"""

    __tablename__ = "analytics_reports"
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)  # trend/pareto/ram/8d/custom
    parameters: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    data: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    generated_by: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    period_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ParetoCache(Base, IDMixin, TenantMixin, TimestampMixin):
    """Pareto 分析缓存（BP-G-03）。"""

    __tablename__ = "pareto_caches"
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)  # equipment/process/anomaly/root_cause
    period_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    items: Mapped[list] = mapped_column(JSONBCompat, nullable=False, default=list)
    cumulative_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)


class G2GCycle(Base, IDMixin, TenantMixin, TimestampMixin):
    """G2G 周期（从发现问题到解决问题，BP-G-04）。"""

    __tablename__ = "g2g_cycles"
    event_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    action_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[float] = mapped_column(Float, nullable=True)
    breakdown: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)  # {trigger:5, workflow:30, rca:60, action:120}


class MetricSample(Base, IDMixin, TenantMixin, TimestampMixin):
    """实时指标采样（支撑 RAM / 趋势分析数据源，P1）。"""

    __tablename__ = "metric_samples"
    equipment_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tags: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
