"""去重键计算测试（BP-A-08/10）。"""

from __future__ import annotations

import pytest

from app.domains.trigger.dedup import compute_dedup_key


@pytest.mark.unit
class TestDedupKey:
    def test_none_template_returns_none(self):
        assert compute_dedup_key(None, {"equipment_id": "EQP-01"}) is None
        assert compute_dedup_key("", {"equipment_id": "EQP-01"}) is None

    def test_simple_template(self):
        key = compute_dedup_key("{equipment_id}", {"equipment_id": "EQP-01"})
        assert key == "EQP-01"

    def test_composite_template(self):
        key = compute_dedup_key("{equipment_id}:{source}", {"equipment_id": "EQP-01", "source": "spc"})
        assert key == "EQP-01:spc"

    def test_missing_var_becomes_empty(self):
        key = compute_dedup_key("{equipment_id}:{process_step}", {"equipment_id": "EQP-01"})
        assert key == "EQP-01:"
