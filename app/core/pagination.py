"""通用分页/排序 Schema。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """分页查询参数。"""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=200)
    sort: str | None = Field(default=None, description="排序字段，前缀 - 表示降序")


class Page(BaseModel, Generic[T]):
    """分页结果。"""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def of(cls, items: list[T], total: int, page: int, size: int) -> "Page[T]":
        pages = (total + size - 1) // size if size > 0 else 0
        return cls(items=items, total=total, page=page, size=size, pages=pages)


class ErrorResponse(BaseModel):
    """统一错误响应。"""

    code: str
    message: str
    details: object | None = None
