"""跨域 Schema Mixin。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """统一 ORM 序列化基类。"""

    model_config = ConfigDict(from_attributes=True)


class TimestampOut(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None
