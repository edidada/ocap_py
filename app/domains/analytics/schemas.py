"""BP-G 分析与持续改进域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.common.enums import KpiCode, Period
from app.domains.common.mixins import ORMBase


class KpiSnapshotIn(BaseModel):
    kpi_code: KpiCode
    period: Period = Period.DAILY
    snapshot_at: datetime | None = None
    value: float
    target: float | None = None
    count: int = 0
    group_by: str | None = None


class KpiOut(ORMBase):
    id: int
    tenant_id: int
    kpi_code: str
    period: str
    snapshot_at: datetime
    value: float
    target: float | None
    count: int
    group_by: str | None


class KpiTrendPoint(BaseModel):
    timestamp: datetime
    value: float
    target: float | None = None


class KpiTrend(BaseModel):
    kpi_code: str
    period: str
    points: list[KpiTrendPoint] = Field(default_factory=list)


class ParetoItem(BaseModel):
    key: str
    value: float
    percent: float
    cumulative: float


class ParetoAnalysis(BaseModel):
    dimension: str
    period_from: datetime
    period_to: datetime
    items: list[ParetoItem] = Field(default_factory=list)
    total: float = 0.0


class G2GStats(BaseModel):
    avg_minutes: float
    median_minutes: float
    p95_minutes: float
    total_cycles: int
    avg_breakdown: dict = Field(default_factory=dict)


class Report8D(BaseModel):
    """8D 纠正预防措施报告（IATF 16949）。"""

    d1_team: str = ""
    d2_problem: str = ""
    d3_containment: str = ""
    d4_root_cause: str = ""
    d5_corrective: str = ""
    d6_implement: str = ""
    d7_preventive: str = ""
    d8_recognition: str = ""
    event_id: int | None = None
    generated_at: datetime | None = None


class RamAnalysis(BaseModel):
    """设备 RAM 分析（SEMI E10）。"""

    equipment_id: str
    availability: float
    reliability_mtbf_hours: float
    maintainability_mttr_minutes: float
    period_from: datetime
    period_to: datetime
