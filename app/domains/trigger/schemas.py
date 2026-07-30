"""BP-A 触发域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.common.enums import EventSource, EventStatus, Severity
from app.domains.common.mixins import ORMBase


class TriggerRuleCreate(BaseModel):
    code: str
    name: str = ""
    source: EventSource
    condition: dict = Field(default_factory=dict)
    priority: int = 0
    debounce_window_s: int = 0
    dedup_key_tpl: str | None = None
    enabled: bool = True
    workflow_template_code: str | None = None


class TriggerRuleUpdate(BaseModel):
    name: str | None = None
    condition: dict | None = None
    priority: int | None = None
    debounce_window_s: int | None = None
    dedup_key_tpl: str | None = None
    enabled: bool | None = None
    workflow_template_code: str | None = None


class TriggerRuleOut(ORMBase):
    id: int
    tenant_id: int
    code: str
    name: str
    source: str
    condition: dict
    priority: int
    debounce_window_s: int
    dedup_key_tpl: str | None
    enabled: bool
    workflow_template_code: str | None
    version: int


class EventCreate(BaseModel):
    source: EventSource = EventSource.MANUAL
    source_event_id: str | None = None
    severity: Severity = Severity.WARNING
    detected_at: datetime | None = None
    equipment_id: str | None = None
    process_step: str | None = None
    parameters: dict = Field(default_factory=dict)
    title: str = ""


class EventIngest(BaseModel):
    """来自三方系统的事件接入。"""

    source: EventSource
    source_event_id: str | None = None
    severity: Severity = Severity.WARNING
    detected_at: datetime | None = None
    equipment_id: str | None = None
    process_step: str | None = None
    parameters: dict = Field(default_factory=dict)
    title: str = ""


class EventAdvance(BaseModel):
    status: EventStatus


class EventOut(ORMBase):
    id: int
    tenant_id: int
    source: str
    source_event_id: str | None
    severity: str
    detected_at: datetime
    equipment_id: str | None
    process_step: str | None
    parameters: dict
    trigger_rule_id: int | None
    status: str
    merged_into_id: int | None
    dedup_key: str | None
    title: str


class IngestResult(BaseModel):
    event_id: int
    created: bool
    merged_into: int | None = None
    dedup_count: int = 1
    trigger_rule_id: int | None = None
