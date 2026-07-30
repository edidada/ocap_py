"""BP-C 根因分析域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.common.enums import RcaMethod, RcaStatus
from app.domains.common.mixins import ORMBase


class RcaCreate(BaseModel):
    event_id: int
    instance_id: int | None = None
    method: RcaMethod = RcaMethod.CPM


class RcaUpdate(BaseModel):
    root_cause: str | None = None
    conclusion: str | None = None
    status: RcaStatus | None = None


class RcaOut(ORMBase):
    id: int
    tenant_id: int
    event_id: int
    instance_id: int | None
    method: str
    status: str
    root_cause: str
    conclusion: str
    created_by: int | None
    concluded_at: datetime | None


class FiveWhyEntry(BaseModel):
    level: int = Field(ge=1, le=5)
    question: str
    answer: str = ""


class FiveWhyOut(ORMBase):
    id: int
    rca_id: int
    level: int
    question: str
    answer: str


class FishboneEntry(BaseModel):
    category: str  # man/machine/material/method/measurement/mother_nature
    cause: str


class FishboneOut(ORMBase):
    id: int
    rca_id: int
    category: str
    cause: str


class DataCorrelationEntry(BaseModel):
    source: str
    parameter: str
    correlation: str = ""
    evidence: dict = Field(default_factory=dict)


class DataCorrelationOut(ORMBase):
    id: int
    rca_id: int
    source: str
    parameter: str
    correlation: str
    evidence: dict


class CpmRequest(BaseModel):
    """上下文模式匹配请求。"""

    event_id: int
    context: dict = Field(default_factory=dict, description="设备/工序/参数/异常类型等上下文特征")


class CpmMatch(BaseModel):
    case_id: int
    score: int  # 0-100
    matched_features: list[str] = Field(default_factory=list)


class CpmResult(ORMBase):
    id: int
    tenant_id: int
    event_id: int
    rca_id: int | None
    context: dict
    matched_cases: list
    top_score: int


class RepeatResult(BaseModel):
    """重复异常识别结果。"""

    event_id: int
    fingerprint: str
    repeat_count: int
    is_systemic: bool
