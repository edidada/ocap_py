"""工作流可视化：生成节点状态视图。"""

from __future__ import annotations

from app.workflow_engine.types import Context, NodeStatus


def render_status(sm, ctx: Context) -> list[dict[str, str]]:
    """返回所有节点及其当前状态。"""
    result = []
    for key, node in sm.nodes.items():
        result.append(
            {
                "key": key,
                "type": node.type.value,
                "name": node.name,
                "status": ctx.statuses.get(key, NodeStatus.PENDING.value),
            }
        )
    return result


def to_mermaid(sm, ctx: Context | None = None) -> str:
    """生成 Mermaid flowchart 字符串（带状态样式）。"""
    lines = ["flowchart TD"]
    for key, node in sm.nodes.items():
        shape = {
            "start": "([{}])",
            "end": "([[{}]])",
            "decision": "{{{}}}",
            "fork": "[[{}]]",
            "join": "[[{}]]",
            "merge": "[[{}]]",
            "wait": "[/{} /]",
            "task": "[{}]",
        }.get(node.type.value, "[{}]")
        lines.append(f'    {key}{shape.format(node.name or key)}')
    for t in sm.transitions:
        label = t.label or t.guard or ""
        suffix = f"|{label}|" if label else ""
        lines.append(f"    {t.from_} -->{suffix} {t.to}")
    if ctx is not None:
        for k, s in ctx.statuses.items():
            if s == NodeStatus.ACTIVE.value:
                lines.append(f"    class {k} active")
            elif s == NodeStatus.COMPLETED.value:
                lines.append(f"    class {k} done")
    return "\n".join(lines)
