"""集成客户端抽象基类。"""

from __future__ import annotations

from abc import ABC

from app.integrations.dtos import HealthDTO


class IntegrationClient(ABC):
    """三方系统集成客户端抽象。各系统子类扩展专属方法。"""

    system_code: str = ""

    async def health(self) -> HealthDTO:
        """健康检查。"""
        return HealthDTO(system=self.system_code, status="up", latency_ms=0)
