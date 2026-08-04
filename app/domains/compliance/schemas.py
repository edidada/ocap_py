"""BP-H 合规与审计域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.common.enums import AuditAction, ConfigItemScope
from app.domains.common.mixins import ORMBase


class AuditOut(ORMBase):
    id: int
    tenant_id: int
    user_id: int | None
    action: str
    resource_type: str
    resource_id: int | None
    path: str
    ip_address: str
    before: dict
    after: dict
    created_at: datetime


class RetentionPolicyIn(BaseModel):
    record_type: str
    retain_days: int = 365 * 7
    disposal_action: str = "archive"
    review_required: bool = True
    enabled: bool = True


class RetentionPolicyOut(ORMBase):
    id: int
    tenant_id: int
    record_type: str
    retain_days: int
    disposal_action: str
    review_required: bool
    enabled: bool


class SpcSpecIn(BaseModel):
    chart_id: str
    parameter: str
    ucl: float
    lcl: float
    target: float
    usl: float | None = None
    lsl: float | None = None
    sample_size: int = 5
    comment_rules: str = ""


class SpcSpecOut(ORMBase):
    id: int
    tenant_id: int
    chart_id: str
    parameter: str
    ucl: float
    lcl: float
    target: float
    usl: float | None
    lsl: float | None
    sample_size: int
    comment_rules: str
    approved_by: int | None
    approved_at: datetime | None
    version: int


class ERecordOut(ORMBase):
    id: int
    tenant_id: int
    record_type: str
    reference_id: int
    content_hash: str
    retained_until: datetime | None
    created_at: datetime


class ESignatureOut(ORMBase):
    id: int
    tenant_id: int
    record_id: int
    user_id: int
    meaning: str
    signed_at: datetime
    signature_hash: str


class ConfigItemIn(BaseModel):
    scope: ConfigItemScope = ConfigItemScope.TENANT
    key: str
    value: dict = Field(default_factory=dict)
    description: str = ""
    enabled: bool = True


class ConfigItemOut(ORMBase):
    id: int
    tenant_id: int
    scope: str
    key: str
    value: dict
    description: str
    enabled: bool
