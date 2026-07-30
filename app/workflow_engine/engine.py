"""BPMN-lite 状态机引擎。

支持：串行、FORK 并行、JOIN 会签（全完成）、MERGE 或签（任一）、
DECISION 动态决策树（guard 自动匹配或人工 take_decision）、WAIT、END。
"""

from __future__ import annotations

from app.core.exceptions import OcapError
from app.workflow_engine.expressions import eval_guard
from app.workflow_engine.types import Context, Node, NodeStatus, NodeType, Transition


class StateMachine:
    """工作流状态机。"""

    def __init__(self, nodes: list[Node] | dict[str, Node], transitions: list[Transition], initial: str):
        self.nodes: dict[str, Node] = {n.key: n for n in nodes} if not isinstance(nodes, dict) else dict(nodes)
        self.transitions = list(transitions)
        self.initial = initial
        self._end_keys = {k for k, n in self.nodes.items() if n.type == NodeType.END}
        if initial not in self.nodes:
            raise OcapError(f"初始节点不存在: {initial}")

    # ---------- 推进 ----------

    def start(self, ctx: Context) -> list[str]:
        """启动工作流，返回激活的节点。"""
        return self._activate(self.initial, ctx)

    def complete_task(self, ctx: Context, node_key: str, output: dict | None = None) -> list[str]:
        """完成一个活跃的 TASK/WAIT 节点，返回新激活的节点。"""
        self._assert_active(ctx, node_key)
        ctx.variables.setdefault("outputs", {})[node_key] = output or {}
        ctx.statuses[node_key] = NodeStatus.COMPLETED.value
        ctx.history.append({"node": node_key, "status": NodeStatus.COMPLETED.value, "output": output or {}})
        return self._evaluate_outgoing(node_key, ctx)

    def take_decision(self, ctx: Context, node_key: str, choice: str) -> list[str]:
        """为活跃的 DECISION 节点提供选择，匹配 label==choice 的转移。"""
        self._assert_active(ctx, node_key)
        outs = [t for t in self._outgoing(node_key) if t.label == choice]
        if not outs:
            raise OcapError(f"节点 {node_key} 无匹配选项 {choice} 的转移")
        ctx.variables.setdefault("decisions", {})[node_key] = choice
        ctx.statuses[node_key] = NodeStatus.COMPLETED.value
        ctx.history.append({"node": node_key, "status": NodeStatus.COMPLETED.value, "decision": choice})
        return self._activate(outs[0].to, ctx)

    def skip_task(self, ctx: Context, node_key: str, reason: str = "") -> list[str]:
        """跳过一个活跃节点（人工干预）。"""
        self._assert_active(ctx, node_key)
        ctx.statuses[node_key] = NodeStatus.SKIPPED.value
        ctx.history.append({"node": node_key, "status": NodeStatus.SKIPPED.value, "reason": reason})
        return self._evaluate_outgoing(node_key, ctx)

    def jump_to(self, ctx: Context, node_key: str) -> list[str]:
        """人工跳转到指定节点（干预）。"""
        if node_key not in self.nodes:
            raise OcapError(f"目标节点不存在: {node_key}")
        ctx.history.append({"action": "jump", "to": node_key})
        return self._activate(node_key, ctx)

    # ---------- 查询 ----------

    def is_terminal(self, ctx: Context) -> bool:
        """是否到达 END 终态。"""
        return any(ctx.is_completed(k) for k in self._end_keys)

    def active_nodes(self, ctx: Context) -> list[str]:
        return ctx.active_nodes()

    def _join_ready(self, ctx: Context, join_key: str) -> bool:
        preds = {t.from_ for t in self.transitions if t.to == join_key}
        return all(ctx.is_completed(p) for p in preds)

    # ---------- 内部 ----------

    def _outgoing(self, key: str) -> list[Transition]:
        return sorted([t for t in self.transitions if t.from_ == key], key=lambda t: -t.priority)

    def _assert_active(self, ctx: Context, key: str) -> None:
        if not ctx.is_active(key):
            raise OcapError(f"节点 {key} 非活跃状态，无法操作（当前: {ctx.statuses.get(key)}）")

    def _activate(self, key: str, ctx: Context) -> list[str]:
        node = self.nodes[key]
        if node.type == NodeType.END:
            ctx.statuses[key] = NodeStatus.COMPLETED.value
            ctx.history.append({"node": key, "status": NodeStatus.COMPLETED.value})
            return [key]
        if node.type in (NodeType.START, NodeType.MERGE):
            ctx.statuses[key] = NodeStatus.COMPLETED.value
            ctx.history.append({"node": key, "status": NodeStatus.COMPLETED.value})
            return self._evaluate_outgoing(key, ctx)
        if node.type == NodeType.FORK:
            ctx.statuses[key] = NodeStatus.COMPLETED.value
            ctx.history.append({"node": key, "status": NodeStatus.COMPLETED.value})
            activated: list[str] = []
            for t in self._outgoing(key):
                activated.extend(self._activate(t.to, ctx))
            return activated
        if node.type == NodeType.JOIN:
            if self._join_ready(ctx, key):
                ctx.statuses[key] = NodeStatus.COMPLETED.value
                ctx.history.append({"node": key, "status": NodeStatus.COMPLETED.value})
                return self._evaluate_outgoing(key, ctx)
            ctx.statuses[key] = NodeStatus.ACTIVE.value
            ctx.history.append({"node": key, "status": NodeStatus.ACTIVE.value})
            return [key]
        # TASK / DECISION / WAIT -> 活跃
        ctx.statuses[key] = NodeStatus.ACTIVE.value
        ctx.history.append({"node": key, "status": NodeStatus.ACTIVE.value})
        if node.type == NodeType.DECISION:
            for t in self._outgoing(key):
                if t.guard and eval_guard(t.guard, ctx):
                    ctx.statuses[key] = NodeStatus.COMPLETED.value
                    ctx.history.append({"node": key, "status": NodeStatus.COMPLETED.value, "auto": t.label})
                    return self._activate(t.to, ctx)
        return [key]

    def _evaluate_outgoing(self, key: str, ctx: Context) -> list[str]:
        for t in self._outgoing(key):
            if eval_guard(t.guard, ctx):
                return self._activate(t.to, ctx)
        return []
