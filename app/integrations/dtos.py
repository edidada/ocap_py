"""集成 DTO：与三方系统交互的数据传输对象。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthDTO(BaseModel):
    system: str
    status: str = "up"
    latency_ms: int = 0


class SpcChartDTO(BaseModel):
    chart_id: str
    parameter: str
    ucl: float
    lcl: float
    target: float
    last_ooc_at: datetime | None = None
    last_value: float | None = None


class SpcEventDTO(BaseModel):
    event_id: str
    chart_id: str
    parameter: str
    value: float
    violation: str
    detected_at: datetime
    severity: str = "warning"
    equipment_id: str | None = None


class FdcAlarmDTO(BaseModel):
    alarm_id: str
    equipment_id: str
    fault: str
    severity: str = "warning"
    detected_at: datetime
    context: dict = Field(default_factory=dict)


class BatchDTO(BaseModel):
    batch_id: str
    product: str
    status: str = "running"  # running | held | released | scrapped | rework
    equipment_id: str | None = None
    quantity: int = 25


class RecipeDTO(BaseModel):
    recipe_id: str
    name: str
    version: int = 1
    params: dict = Field(default_factory=dict)


class MaintenanceOrderDTO(BaseModel):
    order_id: str
    equipment_id: str
    type: str = "corrective"
    status: str = "open"  # open | in_progress | done
    created_at: datetime | None = None


class YieldDTO(BaseModel):
    batch_id: str
    yield_rate: float
    measured_at: datetime | None = None


class DefectDTO(BaseModel):
    defect_id: str
    batch_id: str
    defect_type: str
    count: int
    measured_at: datetime | None = None


class AlarmDTO(BaseModel):
    alarm_id: str
    equipment_id: str
    code: str
    severity: str = "warning"
    raised_at: datetime
    cleared_at: datetime | None = None


class DispositionResultDTO(BaseModel):
    success: bool
    batch_id: str
    new_status: str
    message: str = ""


class RecipeChangeResultDTO(BaseModel):
    success: bool
    recipe_id: str
    new_version: int
    message: str = ""
