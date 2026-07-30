"""BP-D 处置执行域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.common.enums import ActionStatus, ActionType, BatchDisposition
from app.domains.common.mixins import ORMBase


class ActionCreate(BaseModel):
    event_id: int
    rca_id: int | None = None
    instance_id: int | None = None
    type: ActionType
    title: str = ""
    description: str = ""
    assignee_id: int | None = None
    due_at: datetime | None = None
    payload: dict = Field(default_factory=dict)


class ActionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: int | None = None
    due_at: datetime | None = None
    status: ActionStatus | None = None


class ActionOut(ORMBase):
    id: int
    tenant_id: int
    event_id: int
    rca_id: int | None
    instance_id: int | None
    type: str
    title: str
    description: str
    assignee_id: int | None
    status: str
    due_at: datetime | None
    completed_at: datetime | None
    rolled_back_at: datetime | None
    payload: dict


class ExecutionOut(ORMBase):
    id: int
    action_id: int
    actor_id: int | None
    status: str
    detail: str
    result: dict


class SignRequest(BaseModel):
    """电子签核请求。"""

    meaning: str = "approve"


class SignatureOut(ORMBase):
    id: int
    action_id: int
    signer_user_id: int
    meaning: str
    prev_hash: str
    signature_hash: str
    signed_at: datetime


class SlaCreate(BaseModel):
    action_type: ActionType
    target_minutes: int = Field(ge=1)
    warning_minutes: int = Field(default=0, ge=0)
    escalation_role: str | None = None


class SlaOut(ORMBase):
    id: int
    tenant_id: int
    action_type: str
    target_minutes: int
    warning_minutes: int
    escalation_role: str | None


class BatchDispositionRequest(BaseModel):
    batch_id: str
    disposition: BatchDisposition
    reason: str = ""


class BatchDispositionOut(ORMBase):
    id: int
    action_id: int
    batch_id: str
    disposition: str
    reason: str
    synced: bool


class ClosureRequest(BaseModel):
    passed: bool
    note: str = ""
    evidence: dict = Field(default_factory=dict)


class ClosureOut(ORMBase):
    id: int
    action_id: int
    validator_id: int | None
    passed: bool
    evidence: dict
    note: str


class SlaBreach(BaseModel):
    action_id: int
    title: str
    overdue_minutes: int
    escalation_role: str | None
