"""BP-I 平台域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.core.pagination import PageParams
from app.db.session import get_db
from app.domains.common.enums import AuditAction
from app.domains.compliance import service as compliance_svc
from app.domains.iam.models import User
from app.domains.platform import service as platform_svc
from app.domains.platform.schemas import ExportTaskCreate, ExportTaskOut, NotificationOut

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/notifications", response_model=None)
async def list_notifications(
    page: int = 1,
    page_size: int = 50,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await platform_svc.list_notifications(
        db, tenant_id, user.id, PageParams(page=page, size=min(page_size, 200))
    )


@router.post("/notifications", response_model=NotificationOut, status_code=201)
async def create_notification(
    title: str,
    body: str = "",
    channel: str = "im",
    template: str = "generic",
    user_id: int | None = None,
    tenant_id: int = Depends(get_tenant_id),
    actor: User = Depends(require_permission("platform:notify:send")),
    db: AsyncSession = Depends(get_db),
):
    notif = await platform_svc.create_notification(
        db, tenant_id, user_id, channel, template, title, body,
    )
    await compliance_svc.write_audit(
        db, tenant_id, actor.id, AuditAction.CREATE, "Notification", notif.id,
        before={}, after={"title": title, "body": body, "channel": channel, "user_id": user_id},
        path="/platform/notifications",
    )
    await db.commit()
    return notif


@router.get("/exports", response_model=list[ExportTaskOut])
async def list_exports(
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("platform:export:read")),
):
    return await platform_svc.list_exports(tenant_id)


@router.post("/exports", response_model=ExportTaskOut, status_code=201)
async def create_export(
    payload: ExportTaskCreate,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("platform:export:create")),
    db: AsyncSession = Depends(get_db),
):
    task = await platform_svc.create_export(db, tenant_id, user.id, payload)
    await compliance_svc.write_audit(
        db, tenant_id, user.id, AuditAction.CREATE, "ExportTask", task.id,
        before={}, after=payload.model_dump(),
        path="/platform/exports",
    )
    await db.commit()
    return task
