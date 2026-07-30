"""健康检查接口测试."""

import pytest


@pytest.mark.unit
async def test_health_check(client):
    """健康检查应返回 ok."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
