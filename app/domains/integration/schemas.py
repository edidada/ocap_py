"""BP-E 数据集成域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.common.enums import IntegrationMode, IntegrationSystem, SyncDirection
from app.domains.common.mixins import ORMBase


class IntegrationConfigCreate(BaseModel):
    system: IntegrationSystem
    mode: IntegrationMode = IntegrationMode.MOCK
    endpoint: str = ""
    credentials: dict = Field(default_factory=dict)
    enabled: bool = True
    poll_interval_s: int = 60


class IntegrationConfigUpdate(BaseModel):
    mode: IntegrationMode | None = None
    endpoint: str | None = None
    credentials: dict | None = None
    enabled: bool | None = None
    poll_interval_s: int | None = None


class IntegrationConfigOut(ORMBase):
    id: int
    tenant_id: int
    system: str
    mode: str
    endpoint: str
    credentials: dict
    enabled: bool
    poll_interval_s: int


class SyncLogOut(ORMBase):
    id: int
    tenant_id: int
    system: str
    direction: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    records_count: int
    error: str


class SyncResult(BaseModel):
    log_id: int
    system: str
    status: str
    records_count: int
    error: str = ""


class HealthResult(BaseModel):
    system: str
    status: str
    latency_ms: int = 0


class DataQualityIssueOut(ORMBase):
    id: int
    tenant_id: int
    source: str
    metric: str
    score: float
    detected_at: datetime
    resolved: bool
    details: dict


class EventStreamIngest(BaseModel):
    source: IntegrationSystem
    event_type: str
    payload: dict = Field(default_factory=dict)
