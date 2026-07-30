"""健康检查接口."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict[str, str]:
    """健康检查端点."""
    return {"status": "ok"}
