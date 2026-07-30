"""跨方言类型适配（TypeDecorator）。

保证同一套 ORM 模型既能在 PostgreSQL 生产环境运行，也能在 SQLite 内存库
单元测试中运行。关键约束：service 层禁止使用 PG-only 操作符（``->>``、``@>``、
ARRAY 等），JSON 字段统一在 Python 层解析。
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import CHAR, BigInteger, Integer, JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Dialect


class JSONBCompat(TypeDecorator):
    """JSONB on PostgreSQL, JSON (TEXT) elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class ChoiceType(TypeDecorator):
    """Enum 字段：存 ``.value``，读回还原为枚举实例。跨方言兼容。"""

    impl = String
    cache_ok = True

    def __init__(self, enum_cls: type[enum.Enum], length: int = 64, **kwargs: Any):
        self.enum_cls = enum_cls
        super().__init__(length=length, **kwargs)

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value.value
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:  # type: ignore[override]
        if value is None:
            return None
        try:
            return self.enum_cls(value)
        except ValueError:
            return value


class Guid(TypeDecorator):
    """UUID on PostgreSQL, CHAR(32) hex elsewhere."""

    impl = CHAR(32)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:  # type: ignore[override]
        if value is None:
            return None
        if dialect.name == "postgresql":
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(str(value))
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(str(value)).hex

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class BigIntVariant(TypeDecorator):
    """BigInteger on PostgreSQL, Integer on SQLite（自增主键兼容）。"""

    impl = BigInteger
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):  # type: ignore[override]
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Integer())
        return dialect.type_descriptor(BigInteger())
