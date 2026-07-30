"""BP-A 规则引擎：条件匹配与规则选取（BP-A-09）。"""

from __future__ import annotations

from typing import Any

from app.domains.trigger.models import TriggerRule


def match_condition(condition: dict[str, Any], data: dict[str, Any]) -> bool:
    """条件匹配。list 视为「in」，标量视为相等。所有条件需同时满足。"""
    for key, expected in condition.items():
        actual = data.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif isinstance(expected, dict):
            # 区间：{"min": x, "max": y}
            lo, hi = expected.get("min"), expected.get("max")
            if actual is None:
                return False
            if lo is not None and actual < lo:
                return False
            if hi is not None and actual > hi:
                return False
        else:
            if actual != expected:
                return False
    return True


def select_rule(rules: list[TriggerRule], source: str, data: dict[str, Any]) -> TriggerRule | None:
    """从启用规则中选取优先级最高且匹配的规则。"""
    candidates = [r for r in rules if r.enabled and r.source == source]
    candidates.sort(key=lambda r: -r.priority)
    for rule in candidates:
        if match_condition(rule.condition, data):
            return rule
    return None
