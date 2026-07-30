"""BP-A 去重去抖（BP-A-08/10）。"""

from __future__ import annotations

import re
from typing import Any

_VAR_RE = re.compile(r"\{(\w+)\}")


def compute_dedup_key(tpl: str | None, data: dict[str, Any]) -> str | None:
    """根据模板计算去重键。模板如 ``{equipment_id}:{source}``。无模板返回 None。"""
    if not tpl:
        return None

    def _replace(match: re.Match[str]) -> str:
        return str(data.get(match.group(1), ""))

    return _VAR_RE.sub(_replace, tpl)
