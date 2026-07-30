"""工作流引擎核心抽象：节点、转移、上下文。"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class NodeType(str, enum.Enum):
    START = "start"
    TASK = "task"
    DECISION = "decision"
    FORK = "fork"
    JOIN = "join"
    MERGE = "merge"
    WAIT = "wait"
    END = "end"


class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class Node:
    """工作流节点。"""

    key: str
    type: NodeType
    name: str = ""
    assignee_role: str | None = None
    timeout_s: int | None = None
    on_enter: list[str] = field(default_factory=list)
    on_exit: list[str] = field(default_factory=list)
    decision_tree: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Transition:
    """节点间转移。guard 为表达式字符串，求值于 ctx；label 用于 DECISION 选项。"""

    from_: str
    to: str
    guard: str | None = None
    label: str = ""
    priority: int = 0


@dataclass
class Context:
    """工作流执行上下文（内存态，可序列化持久化）。"""

    instance_id: int | None = None
    tenant_id: int | None = None
    event: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    statuses: dict[str, str] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    def is_completed(self, key: str) -> bool:
        return self.statuses.get(key) == NodeStatus.COMPLETED.value

    def is_active(self, key: str) -> bool:
        return self.statuses.get(key) == NodeStatus.ACTIVE.value

    def active_nodes(self) -> list[str]:
        return [k for k, s in self.statuses.items() if s == NodeStatus.ACTIVE.value]

    def to_snapshot(self) -> dict[str, Any]:
        """用于持久化的快照。"""
        return {
            "event": self.event,
            "variables": self.variables,
            "statuses": self.statuses,
            "history": self.history,
        }

    @classmethod
    def from_snapshot(cls, snap: dict[str, Any], *, instance_id: int | None = None) -> "Context":
        return cls(
            instance_id=instance_id,
            event=snap.get("event", {}),
            variables=snap.get("variables", {}),
            statuses=snap.get("statuses", {}),
            history=snap.get("history", []),
        )
