"""BP-F 知识管理域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.common.enums import KnowledgeCaseStatus
from app.domains.common.mixins import ORMBase


class CaseCreate(BaseModel):
    code: str
    title: str = ""
    event_id: int | None = None
    equipment_id: str | None = None
    process_step: str | None = None
    anomaly_type: str | None = None
    root_cause: str = ""
    solution: str = ""
    context: dict = Field(default_factory=dict)


class CaseUpdate(BaseModel):
    title: str | None = None
    root_cause: str | None = None
    solution: str | None = None
    context: dict | None = None
    status: KnowledgeCaseStatus | None = None


class CaseOut(ORMBase):
    id: int
    tenant_id: int
    code: str
    title: str
    event_id: int | None
    equipment_id: str | None
    process_step: str | None
    anomaly_type: str | None
    root_cause: str
    solution: str
    context: dict
    status: str
    published_at: datetime | None
    published_by: int | None


class CaseSearchResult(BaseModel):
    case: CaseOut
    score: int = 0
    matched_features: list[str] = Field(default_factory=list)


class SolutionTemplateCreate(BaseModel):
    code: str
    title: str = ""
    anomaly_type: str | None = None
    steps: list[str] = Field(default_factory=list)
    applicable_context: dict = Field(default_factory=dict)
    enabled: bool = True


class SolutionTemplateOut(ORMBase):
    id: int
    tenant_id: int
    code: str
    title: str
    anomaly_type: str | None
    steps: list
    applicable_context: dict
    enabled: bool


class GraphNodeCreate(BaseModel):
    node_type: str
    name: str
    attributes: dict = Field(default_factory=dict)


class GraphNodeOut(ORMBase):
    id: int
    tenant_id: int
    node_type: str
    name: str
    attributes: dict


class GraphEdgeCreate(BaseModel):
    from_node_id: int
    to_node_id: int
    relation: str
    weight: float = 1.0


class GraphEdgeOut(ORMBase):
    id: int
    tenant_id: int
    from_node_id: int
    to_node_id: int
    relation: str
    weight: float
