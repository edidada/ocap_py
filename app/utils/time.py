"""时间工具。"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """当前 UTC 时间。便于测试通过 time-machine 注入。"""
    return datetime.now(timezone.utc)
