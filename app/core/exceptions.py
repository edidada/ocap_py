"""全局异常体系与 FastAPI 异常处理。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class OcapError(Exception):
    """OCAP 业务异常基类。"""

    def __init__(self, message: str, code: str = "OCAP_ERROR", status_code: int = 400, details: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(OcapError):
    def __init__(self, message: str = "资源不存在", details: Any = None):
        super().__init__(message, code="NOT_FOUND", status_code=404, details=details)


class ValidationFailed(OcapError):
    def __init__(self, message: str = "校验失败", details: Any = None):
        super().__init__(message, code="VALIDATION_FAILED", status_code=422, details=details)


class ConflictError(OcapError):
    def __init__(self, message: str = "冲突", details: Any = None):
        super().__init__(message, code="CONFLICT", status_code=409, details=details)


class OptimisticLockError(OcapError):
    def __init__(self, message: str = "并发冲突，请重试", details: Any = None):
        super().__init__(message, code="OPTIMISTIC_LOCK", status_code=409, details=details)


class PermissionDenied(OcapError):
    def __init__(self, message: str = "无权限", details: Any = None):
        super().__init__(message, code="PERMISSION_DENIED", status_code=403, details=details)


class AuthError(OcapError):
    def __init__(self, message: str = "认证失败", details: Any = None):
        super().__init__(message, code="AUTH_ERROR", status_code=401, details=details)


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常处理。"""

    @app.exception_handler(OcapError)
    async def _handle_ocap_error(_: Request, exc: OcapError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )
