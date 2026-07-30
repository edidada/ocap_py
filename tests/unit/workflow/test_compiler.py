"""模板编译器与可视化测试。"""

from __future__ import annotations

import pytest

from app.workflow_engine.compiler import compile_template, validate_template
from app.workflow_engine.engine import StateMachine
from app.workflow_engine.types import Context, NodeType
from app.workflow_engine.visualizer import render_status, to_mermaid


def _template() -> dict:
    return {
        "initial": "start",
        "nodes": [
            {"key": "start", "type": "start", "name": "开始"},
            {"key": "investigate", "type": "task", "name": "排查", "assignee_role": "engineer"},
            {"key": "end", "type": "end", "name": "结束"},
        ],
        "transitions": [
            {"from": "start", "to": "investigate"},
            {"from": "investigate", "to": "end"},
        ],
    }


@pytest.mark.unit
class TestCompiler:
    def test_compile_returns_state_machine(self):
        sm = compile_template(_template())
        assert isinstance(sm, StateMachine)
        assert sm.initial == "start"
        assert sm.nodes["investigate"].type == NodeType.TASK
        assert sm.nodes["investigate"].assignee_role == "engineer"

    def test_compile_and_run(self):
        sm = compile_template(_template())
        ctx = Context()
        sm.start(ctx)
        sm.complete_task(ctx, "investigate")
        assert sm.is_terminal(ctx)

    def test_compile_invalid_missing_fields(self):
        from app.core.exceptions import ValidationFailed

        with pytest.raises(ValidationFailed):
            compile_template({"initial": "start"})

    def test_validate_template_missing_end(self):
        tpl = _template()
        tpl["nodes"] = [n for n in tpl["nodes"] if n["type"] != "end"]
        errors = validate_template(tpl)
        assert any("end" in e for e in errors)

    def test_validate_template_bad_transition(self):
        tpl = _template()
        tpl["transitions"].append({"from": "ghost", "to": "end"})
        errors = validate_template(tpl)
        assert any("ghost" in e for e in errors)


@pytest.mark.unit
class TestVisualizer:
    def test_render_status(self):
        sm = compile_template(_template())
        ctx = Context()
        sm.start(ctx)
        statuses = {n["key"]: n["status"] for n in render_status(sm, ctx)}
        assert statuses["start"] == "completed"
        assert statuses["investigate"] == "active"
        assert statuses["end"] == "pending"

    def test_to_mermaid_contains_nodes_and_edges(self):
        sm = compile_template(_template())
        mermaid = to_mermaid(sm)
        assert "flowchart TD" in mermaid
        assert "start -->" in mermaid
        assert "investigate --> end" in mermaid
