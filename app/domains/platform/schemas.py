"""BP-I 平台域 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: int
    user_id: int | None
    channel: str
    template: str
    title: str
    body: str
    status: str
    sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportTaskOut(BaseModel):
    id: int
    tenant_id: int
    resource: str
    format: str
    status: str
    file_path: str | None
    created_by: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportTaskCreate(BaseModel):
    resource: str
    format: str = "csv"
    parameters: dict = Field(default_factory=dict)
