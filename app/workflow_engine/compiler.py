"""模板定义 -> StateMachine 编译器。

模板定义结构（JSON/dict）：
    {
        "initial": "start",
        "nodes": [
            {"key": "start", "type": "start", "name": "开始"},
            {"key": "investigate", "type": "task", "name": "排查", "assignee_role": "engineer", "timeout_s": 3600},
            {"key": "severity?", "type": "decision", "name": "严重度判定"},
            {"key": "end", "type": "end", "name": "结束"}
        ],
        "transitions": [
            {"from": "start", "to": "investigate"},
            {"from": "investigate", "to": "severity?"},
            {"from": "severity?", "to": "end", "label": "minor"},
            {"from": "severity?", "to": "end", "label": "major", "guard": "ctx.variables['severity']=='critical'"}
        ]
    }
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationFailed
from app.workflow_engine.engine import StateMachine
from app.workflow_engine.types import Node, NodeType, Transition


def compile_template(definition: dict[str, Any]) -> StateMachine:
    """编译模板定义为 StateMachine。"""
    if not isinstance(definition, dict):
        raise ValidationFailed("模板定义必须为 dict")
    nodes_def = definition.get("nodes")
    transitions_def = definition.get("transitions")
    initial = definition.get("initial")
    if not nodes_def or not transitions_def or not initial:
        raise ValidationFailed("模板必须包含 nodes/transitions/initial")

    nodes: list[Node] = []
    for n in nodes_def:
        nodes.append(
            Node(
                key=n["key"],
                type=NodeType(n["type"]),
                name=n.get("name", ""),
                assignee_role=n.get("assignee_role"),
                timeout_s=n.get("timeout_s"),
                on_enter=n.get("on_enter", []),
                on_exit=n.get("on_exit", []),
                decision_tree=bool(n.get("decision_tree", False)),
                metadata=n.get("metadata", {}),
            )
        )

    transitions = [
        Transition(
            from_=t["from"],
            to=t["to"],
            guard=t.get("guard"),
            label=t.get("label", ""),
            priority=t.get("priority", 0),
        )
        for t in transitions_def
    ]
    return StateMachine(nodes, transitions, initial)


def validate_template(definition: dict[str, Any]) -> list[str]:
    """静态校验模板，返回错误信息列表（空表示通过）。"""
    errors: list[str] = []
    nodes_def = definition.get("nodes", [])
    transitions_def = definition.get("transitions", [])
    initial = definition.get("initial")
    keys = {n["key"] for n in nodes_def}
    if initial and initial not in keys:
        errors.append(f"初始节点 {initial} 不在节点列表中")
    has_start = any(n.get("type") == NodeType.START.value for n in nodes_def)
    has_end = any(n.get("type") == NodeType.END.value for n in nodes_def)
    if not has_start:
        errors.append("缺少 start 节点")
    if not has_end:
        errors.append("缺少 end 节点")
    for t in transitions_def:
        if t.get("from") not in keys:
            errors.append(f"转移 from={t.get('from')} 节点不存在")
        if t.get("to") not in keys:
            errors.append(f"转移 to={t.get('to')} 节点不存在")
    return errors
