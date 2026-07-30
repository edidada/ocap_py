"""BP-B 工作流编排域 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domains.common.mixins import ORMBase


class TemplateCreate(BaseModel):
    code: str
    name: str = ""
    process_step: str | None = None
    anomaly_type: str | None = None
    definition: dict


class TemplateUpdate(BaseModel):
    name: str | None = None
    process_step: str | None = None
    anomaly_type: str | None = None
    definition: dict | None = None


class TemplateOut(ORMBase):
    id: int
    tenant_id: int
    code: str
    name: str
    process_step: str | None
    anomaly_type: str | None
    status: str
    version: int
    definition: dict
    published_at: datetime | None


class StartInstance(BaseModel):
    template_id: int
    event_id: int | None = None
    variables: dict = Field(default_factory=dict)


class InstanceOut(ORMBase):
    id: int
    tenant_id: int
    template_id: int
    template_version: int
    event_id: int | None
    current_node_key: str | None
    status: str
    context: dict
    started_at: datetime
    completed_at: datetime | None


class NodeOut(ORMBase):
    id: int
    instance_id: int
    node_key: str
    node_type: str
    status: str
    assignee_role: str | None
    output: dict


class AdvanceRequest(BaseModel):
    action: Literal["complete_task", "take_decision", "skip", "jump"]
    node_key: str
    output: dict = Field(default_factory=dict)
    choice: str | None = None
    target_node_key: str | None = None
    reason: str = ""


class AdvanceResult(BaseModel):
    instance: InstanceOut
    activated_nodes: list[str]
    terminal: bool


class InterveneRequest(BaseModel):
    type: Literal["skip", "jump", "reassign", "override", "escalation"]
    node_key: str | None = None
    target_node_key: str | None = None
    reason: str = ""


class SopCreate(BaseModel):
    code: str
    title: str
    steps: list[str]


class SopOut(ORMBase):
    id: int
    tenant_id: int
    code: str
    title: str
    steps: list
    version: int
