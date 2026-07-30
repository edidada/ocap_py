"""FastAPI 应用入口."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理."""
    # 启动
    yield
    # 关闭
    await _dispose_resources()


async def _dispose_resources() -> None:
    """释放资源."""
    from app.db.session import engine

    await engine.dispose()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "OCAP (Out-of-Control Action Plan) System - "
            "半导体制造异常失控处置系统，对标 Applied Materials SmartFactory Knowledge Advisor"
        ),
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
