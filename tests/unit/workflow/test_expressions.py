"""guard 表达式安全求值测试。"""

from __future__ import annotations

import pytest

from app.workflow_engine.expressions import eval_guard
from app.workflow_engine.types import Context


@pytest.mark.unit
class TestEvalGuard:
    def test_empty_expr_is_true(self):
        assert eval_guard(None, Context()) is True
        assert eval_guard("", Context()) is True
        assert eval_guard("   ", Context()) is True

    def test_simple_compare(self):
        ctx = Context(variables={"severity": "critical"})
        assert eval_guard("ctx.variables['severity'] == 'critical'", ctx) is True
        assert eval_guard("ctx.variables['severity'] == 'minor'", ctx) is False

    def test_boolean_and(self):
        ctx = Context(event={"source": "spc"}, variables={"severity": "critical"})
        expr = "ctx.event['source'] == 'spc' and ctx.variables['severity'] == 'critical'"
        assert eval_guard(expr, ctx) is True

    def test_in_operator(self):
        ctx = Context(variables={"source": "fdc"})
        assert eval_guard("ctx.variables['source'] in ['spc', 'fdc']", ctx) is True

    def test_syntax_error_returns_false(self):
        assert eval_guard("ctx.variables[", Context()) is False

    def test_runtime_error_returns_false(self):
        ctx = Context(variables={})
        assert eval_guard("ctx.variables['missing'] == 'x'", ctx) is False

    def test_call_is_blocked(self):
        # 函数调用不在白名单中，应返回 False
        assert eval_guard("__import__('os')", Context()) is False
        assert eval_guard("len(ctx.variables)", Context()) is False

    def test_dunder_attribute_blocked(self):
        ctx = Context()
        assert eval_guard("ctx.__class__", ctx) is False

    def test_if_exp(self):
        ctx = Context(variables={"v": 5})
        assert eval_guard("'high' if ctx.variables['v'] > 3 else 'low'", ctx) is True
