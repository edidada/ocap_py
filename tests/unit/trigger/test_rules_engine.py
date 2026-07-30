"""规则引擎测试（BP-A-09）。"""

from __future__ import annotations

import pytest

from app.domains.common.enums import EventSource
from app.domains.trigger.models import TriggerRule
from app.domains.trigger.rules_engine import match_condition, select_rule


def _rule(code: str, source: str, condition: dict, priority: int = 0, enabled: bool = True) -> TriggerRule:
    r = TriggerRule(
        tenant_id=1, code=code, name=code, source=source, condition=condition, priority=priority, enabled=enabled
    )
    r.id = hash(code)  # 仅用于区分
    return r


@pytest.mark.unit
class TestMatchCondition:
    def test_scalar_eq(self):
        assert match_condition({"equipment_id": "EQP-01"}, {"equipment_id": "EQP-01"}) is True
        assert match_condition({"equipment_id": "EQP-01"}, {"equipment_id": "EQP-02"}) is False

    def test_list_in(self):
        assert match_condition({"severity": ["critical", "fatal"]}, {"severity": "critical"}) is True
        assert match_condition({"severity": ["critical"]}, {"severity": "warning"}) is False

    def test_range(self):
        cond = {"value": {"min": 95, "max": 105}}
        assert match_condition(cond, {"value": 100}) is True
        assert match_condition(cond, {"value": 106}) is False
        assert match_condition(cond, {"value": 94}) is False

    def test_multiple_all_must_match(self):
        cond = {"severity": "critical", "equipment_id": "EQP-01"}
        assert match_condition(cond, {"severity": "critical", "equipment_id": "EQP-01"}) is True
        assert match_condition(cond, {"severity": "critical", "equipment_id": "EQP-02"}) is False

    def test_empty_condition_matches(self):
        assert match_condition({}, {"severity": "critical"}) is True


@pytest.mark.unit
class TestSelectRule:
    def test_selects_matching_rule(self):
        rules = [
            _rule("r1", "spc", {"severity": "minor"}),
            _rule("r2", "spc", {"severity": "critical"}),
        ]
        selected = select_rule(rules, "spc", {"severity": "critical"})
        assert selected.code == "r2"

    def test_selects_highest_priority(self):
        rules = [
            _rule("low", "spc", {}, priority=1),
            _rule("high", "spc", {}, priority=10),
        ]
        selected = select_rule(rules, "spc", {})
        assert selected.code == "high"

    def test_filters_by_source(self):
        rules = [_rule("r1", "fdc", {})]
        assert select_rule(rules, "spc", {}) is None

    def test_skips_disabled(self):
        rules = [_rule("r1", "spc", {}, enabled=False)]
        assert select_rule(rules, "spc", {}) is None

    def test_no_match_returns_none(self):
        rules = [_rule("r1", "spc", {"severity": "fatal"})]
        assert select_rule(rules, "spc", {"severity": "warning"}) is None
