"""BP-C 根因分析域 ORM 模型。

支撑：数据关联视图(BP-C-01)、上下文模式匹配 CPM(BP-C-02)、
5-Why/鱼骨图(BP-C-04)、历史案例检索(BP-C-06)、重复异常识别(BP-C-07)。
FTA(BP-C-05) 与知识图谱(BP-C-08) 为 P2，提供模型占位。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import RcaMethod, RcaStatus


class RcaRecord(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """根因分析主记录。"""

    __tablename__ = "rca_records"
    event_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    instance_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default=RcaMethod.CPM.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RcaStatus.IN_PROGRESS.value)
    root_cause: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    conclusion: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RcaFiveWhy(Base, IDMixin, TimestampMixin):
    """5-Why 分析层级。"""

    __tablename__ = "rca_five_why"
    __table_args__ = (UniqueConstraint("rca_id", "level", name="uq_five_why_rca_level"),)
    rca_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("rca_records.id"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    answer: Mapped[str] = mapped_column(String(1024), nullable=False, default="")


class RcaFishbone(Base, IDMixin, TimestampMixin):
    """鱼骨图（Ishikawa）6M 分类根因。"""

    __tablename__ = "rca_fishbone"
    rca_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("rca_records.id"), nullable=False, index=True)
    # 6M: man / machine / material / method / measurement / mother_nature
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    cause: Mapped[str] = mapped_column(String(512), nullable=False, default="")


class RcaDataCorrelation(Base, IDMixin, TimestampMixin):
    """跨系统数据关联视图（BP-C-01）。"""

    __tablename__ = "rca_data_correlations"
    rca_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("rca_records.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # IntegrationSystem.value
    parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    evidence: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class CpmRun(Base, IDMixin, TenantMixin, TimestampMixin):
    """上下文模式匹配运行记录（BP-C-02）。"""

    __tablename__ = "cpm_runs"
    event_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    rca_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    context: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    matched_cases: Mapped[list] = mapped_column(JSONBCompat, nullable=False, default=list)
    top_score: Mapped[float] = mapped_column(Integer, nullable=False, default=0)  # 0-100 整数分


class RepeatDetection(Base, IDMixin, TenantMixin, TimestampMixin):
    """重复异常识别结果（BP-C-07）。"""

    __tablename__ = "repeat_detections"
    event_id: Mapped[int] = mapped_column(BigIntVariant(), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_systemic: Mapped[bool] = mapped_column(default=False)


class RcaFta(Base, IDMixin, TimestampMixin):
    """故障树分析（BP-C-05，P2 占位）。"""

    __tablename__ = "rca_fta"
    rca_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("rca_records.id"), nullable=False, index=True)
    top_event: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    tree: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
