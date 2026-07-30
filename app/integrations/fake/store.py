"""FakeStore：内存数据存储，被所有 fake 客户端共享。

从 ``seed/data/10_fake_store.yaml`` 装载初始数据；测试可单独构造空存储。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.integrations.dtos import (
    AlarmDTO,
    BatchDTO,
    DefectDTO,
    FdcAlarmDTO,
    MaintenanceOrderDTO,
    RecipeDTO,
    SpcChartDTO,
    SpcEventDTO,
    YieldDTO,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class FakeStore:
    """内存数据存储。"""

    def __init__(self) -> None:
        self.batches: dict[str, BatchDTO] = {}
        self.recipes: dict[str, RecipeDTO] = {}
        self.spc_charts: dict[str, SpcChartDTO] = {}
        self.spc_events: list[SpcEventDTO] = []
        self.fdc_alarms: dict[str, FdcAlarmDTO] = {}
        self.ams_alarms: dict[str, AlarmDTO] = {}
        self.yields: dict[str, YieldDTO] = {}
        self.defects: dict[str, DefectDTO] = {}
        self.maintenance_orders: dict[str, MaintenanceOrderDTO] = {}

    @classmethod
    def from_seed(cls, path: str | Path) -> "FakeStore":
        """从 YAML 文件装载初始数据。文件不存在则返回空存储。"""
        store = cls()
        p = Path(path)
        if not p.exists():
            return store
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for b in data.get("batches", []):
            store.batches[b["batch_id"]] = BatchDTO(**b)
        for r in data.get("recipes", []):
            store.recipes[r["recipe_id"]] = RecipeDTO(**r)
        for c in data.get("spc_charts", []):
            c = dict(c)
            if "last_ooc_at" in c:
                c["last_ooc_at"] = _parse_dt(c["last_ooc_at"])
            store.spc_charts[c["chart_id"]] = SpcChartDTO(**c)
        for e in data.get("spc_events", []):
            e = dict(e)
            e["detected_at"] = _parse_dt(e["detected_at"])
            store.spc_events.append(SpcEventDTO(**e))
        for f in data.get("fdc_alarms", []):
            f = dict(f)
            f["detected_at"] = _parse_dt(f["detected_at"])
            store.fdc_alarms[f["alarm_id"]] = FdcAlarmDTO(**f)
        for a in data.get("ams_alarms", []):
            a = dict(a)
            a["raised_at"] = _parse_dt(a["raised_at"])
            a["cleared_at"] = _parse_dt(a.get("cleared_at"))
            store.ams_alarms[a["alarm_id"]] = AlarmDTO(**a)
        for y in data.get("yields", []):
            y = dict(y)
            y["measured_at"] = _parse_dt(y.get("measured_at"))
            store.yields[y["batch_id"]] = YieldDTO(**y)
        for d in data.get("defects", []):
            d = dict(d)
            d["measured_at"] = _parse_dt(d.get("measured_at"))
            store.defects[d["defect_id"]] = DefectDTO(**d)
        for m in data.get("maintenance_orders", []):
            m = dict(m)
            m["created_at"] = _parse_dt(m.get("created_at"))
            store.maintenance_orders[m["order_id"]] = MaintenanceOrderDTO(**m)
        return store

    @classmethod
    def empty(cls) -> "FakeStore":
        return cls()
