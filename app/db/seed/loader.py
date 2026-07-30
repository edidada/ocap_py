"""Seed 加载器：按文件名排序加载 YAML 打底数据，幂等（按主键跳过已存在行）。

YAML 格式：
    - model: app.domains.iam.models.Tenant
      rows:
        - id: 1
          code: fab01
          name: 晶圆厂一
          ...
特殊字段：
    __password__: 明文密码，加载时哈希为 password_hash
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password


class SeedLoader:
    """从目录加载 YAML 种子数据。"""

    def __init__(self, db: AsyncSession, data_dir: str | Path):
        self.db = db
        self.data_dir = Path(data_dir)
        self._model_cache: dict[str, type] = {}

    async def load(self) -> int:
        """加载目录下所有 *.yaml，返回加载行数。"""
        if not self.data_dir.exists():
            return 0
        count = 0
        for path in sorted(self.data_dir.glob("*.yaml")):
            docs = yaml.safe_load(path.read_text(encoding="utf-8"))
            # seed 文件顶层为 list（[{model, rows}, ...]）；非 seed 文件（如 fake_store）为 dict，跳过
            if not isinstance(docs, list):
                continue
            for doc in docs:
                count += await self._load_doc(doc)
        return count

    async def _load_doc(self, doc: dict[str, Any]) -> int:
        model = self._resolve_model(doc["model"])
        rows = doc.get("rows", [])
        n = 0
        for row in rows:
            if await self._upsert(model, row):
                n += 1
        return n

    async def _upsert(self, model: type, row: dict[str, Any]) -> bool:
        pk_cols = [c.name for c in inspect(model).primary_key]
        pk_values = tuple(row.get(c) for c in pk_cols)
        if all(v is not None for v in pk_values):
            existing = await self.db.get(model, pk_values if len(pk_values) > 1 else pk_values[0])
            if existing is not None:
                return False
        fields = {k: v for k, v in row.items() if not k.startswith("__")}
        if "__password__" in row:
            fields["password_hash"] = hash_password(row["__password__"])
        obj = model(**fields)
        self.db.add(obj)
        await self.db.flush()
        return True

    def _resolve_model(self, dotted: str) -> type:
        if dotted not in self._model_cache:
            module_path, _, attr = dotted.rpartition(".")
            module = importlib.import_module(module_path)
            self._model_cache[dotted] = getattr(module, attr)
        return self._model_cache[dotted]
