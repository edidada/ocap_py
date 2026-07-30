"""状态机引擎测试：串行/并行/JOIN/MERGE/DECISION/WAIT/干预。"""

from __future__ import annotations

import pytest

from app.core.exceptions import OcapError
from app.workflow_engine.engine import StateMachine
from app.workflow_engine.types import Context, Node, NodeType, Transition


def _serial_sm() -> StateMachine:
    return StateMachine(
        nodes=[
            Node("start", NodeType.START, "开始"),
            Node("investigate", NodeType.TASK, "排查"),
            Node("fix", NodeType.TASK, "处置"),
            Node("end", NodeType.END, "结束"),
        ],
        transitions=[
            Transition("start", "investigate"),
            Transition("investigate", "fix"),
            Transition("fix", "end"),
        ],
        initial="start",
    )


def _parallel_sm() -> StateMachine:
    return StateMachine(
        nodes=[
            Node("start", NodeType.START),
            Node("fork", NodeType.FORK),
            Node("a", NodeType.TASK, "分支A"),
            Node("b", NodeType.TASK, "分支B"),
            Node("join", NodeType.JOIN),
            Node("end", NodeType.END),
        ],
        transitions=[
            Transition("start", "fork"),
            Transition("fork", "a"),
            Transition("fork", "b"),
            Transition("a", "join"),
            Transition("b", "join"),
            Transition("join", "end"),
        ],
        initial="start",
    )


def _decision_sm() -> StateMachine:
    return StateMachine(
        nodes=[
            Node("start", NodeType.START),
            Node("decide", NodeType.DECISION, "严重度判定"),
            Node("minor_end", NodeType.END, "轻微结束"),
            Node("major_fix", NodeType.TASK, "重大处置"),
            Node("major_end", NodeType.END),
        ],
        transitions=[
            Transition("start", "decide"),
            Transition("decide", "minor_end", label="minor"),
            Transition(
                "decide", "major_fix", label="major", guard="ctx.variables['severity']=='critical'"
            ),
            Transition("major_fix", "major_end"),
        ],
        initial="start",
    )


@pytest.mark.unit
class TestSerial:
    def test_start_activates_first_task(self):
        sm = _serial_sm()
        ctx = Context()
        activated = sm.start(ctx)
        assert activated == ["investigate"]
        assert ctx.is_active("investigate")

    def test_complete_reaches_end(self):
        sm = _serial_sm()
        ctx = Context()
        sm.start(ctx)
        sm.complete_task(ctx, "investigate", {"found": "drift"})
        sm.complete_task(ctx, "fix", {"action": "reset"})
        assert sm.is_terminal(ctx)
        assert ctx.is_completed("end")
        assert ctx.variables["outputs"]["investigate"] == {"found": "drift"}

    def test_complete_non_active_raises(self):
        sm = _serial_sm()
        ctx = Context()
        sm.start(ctx)
        with pytest.raises(OcapError):
            sm.complete_task(ctx, "fix")


@pytest.mark.unit
class TestParallel:
    def test_fork_activates_both_branches(self):
        sm = _parallel_sm()
        ctx = Context()
        sm.start(ctx)
        assert set(ctx.active_nodes()) == {"a", "b"}

    def test_join_waits_for_both(self):
        sm = _parallel_sm()
        ctx = Context()
        sm.start(ctx)
        sm.complete_task(ctx, "a")
        # 只完成 A，JOIN 仍等待 B
        assert ctx.is_active("join")
        assert not sm.is_terminal(ctx)
        sm.complete_task(ctx, "b")
        # 两者完成后 JOIN 自动完成并到达 end
        assert sm.is_terminal(ctx)
        assert ctx.is_completed("end")


@pytest.mark.unit
class TestDecision:
    def test_auto_guard_advances(self):
        sm = _decision_sm()
        ctx = Context(variables={"severity": "critical"})
        sm.start(ctx)
        # DECISION 节点 guard 自动匹配 major 分支
        assert ctx.is_active("major_fix")
        assert ctx.is_completed("decide")

    def test_manual_decision_minor(self):
        sm = _decision_sm()
        ctx = Context(variables={"severity": "minor"})
        sm.start(ctx)
        # 无 guard 匹配（severity != critical），DECISION 保持活跃
        assert ctx.is_active("decide")
        sm.take_decision(ctx, "decide", "minor")
        assert sm.is_terminal(ctx)
        assert ctx.is_completed("minor_end")

    def test_invalid_choice_raises(self):
        sm = _decision_sm()
        ctx = Context(variables={"severity": "minor"})
        sm.start(ctx)
        with pytest.raises(OcapError):
            sm.take_decision(ctx, "decide", "nonexistent")


@pytest.mark.unit
class TestIntervention:
    def test_skip_task(self):
        sm = _serial_sm()
        ctx = Context()
        sm.start(ctx)
        sm.skip_task(ctx, "investigate", "无需排查")
        assert ctx.is_completed("fix") or ctx.is_active("fix")
        sm.complete_task(ctx, "fix")
        assert sm.is_terminal(ctx)

    def test_jump_to(self):
        sm = _serial_sm()
        ctx = Context()
        sm.start(ctx)
        sm.jump_to(ctx, "fix")
        assert ctx.is_active("fix")


@pytest.mark.unit
class TestMerge:
    def test_merge_advances_on_any(self):
        sm = StateMachine(
            nodes=[
                Node("start", NodeType.START),
                Node("fork", NodeType.FORK),
                Node("a", NodeType.TASK),
                Node("b", NodeType.TASK),
                Node("merge", NodeType.MERGE),
                Node("end", NodeType.END),
            ],
            transitions=[
                Transition("start", "fork"),
                Transition("fork", "a"),
                Transition("fork", "b"),
                Transition("a", "merge"),
                Transition("b", "merge"),
                Transition("merge", "end"),
            ],
            initial="start",
        )
        ctx = Context()
        sm.start(ctx)
        sm.complete_task(ctx, "a")
        # MERGE 任一前驱完成即可推进
        assert sm.is_terminal(ctx)


@pytest.mark.unit
class TestWait:
    def test_wait_node_advances_on_complete(self):
        sm = StateMachine(
            nodes=[
                Node("start", NodeType.START),
                Node("wait", NodeType.WAIT, "等待外部事件"),
                Node("end", NodeType.END),
            ],
            transitions=[Transition("start", "wait"), Transition("wait", "end")],
            initial="start",
        )
        ctx = Context()
        sm.start(ctx)
        assert ctx.is_active("wait")
        sm.complete_task(ctx, "wait", {"signal": "ok"})
        assert sm.is_terminal(ctx)
