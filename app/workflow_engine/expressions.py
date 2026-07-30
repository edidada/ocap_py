"""guard 表达式安全求值（AST 白名单）。

表达式形如 ``ctx.variables['severity'] == 'critical' and ctx.event['source'] == 'spc'``，
求值于 Context。禁止函数调用、import、dunder 访问；guard 失败（语法/求值异常）返回 False。
"""

from __future__ import annotations

import ast
from typing import Any

_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.IfExp,
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Load,
    ast.And,
    ast.Or,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Index,
)


def eval_guard(expr: str | None, ctx: Any) -> bool:
    """安全求值 guard 表达式，返回布尔结果。空/异常返回 False。"""
    if not expr or not expr.strip():
        return True
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return False
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return False
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return False
    try:
        result = eval(  # noqa: S307 - 受控白名单求值
            compile(tree, "<guard>", "eval"),
            {"__builtins__": {}},
            {"ctx": ctx, "True": True, "False": False, "None": None},
        )
    except Exception:
        return False
    return bool(result)
