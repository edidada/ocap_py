"""BP-I 平台域服务：通知/导出/任务调度(BP-I-08/09)。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PageParams
from app.domains.compliance.models import ConfigItem, Notification
from app.domains.platform.schemas import ExportTaskCreate
from app.utils.time import utcnow


# ----------------------------- 通知 -----------------------------


async def list_notifications(
    db: AsyncSession, tenant_id: int, user_id: int | None, params: PageParams
) -> Page[Notification]:
    stmt = select(Notification).where(Notification.tenant_id == tenant_id)
    if user_id is not None:
        stmt = stmt.where(Notification.user_id == user_id)
    stmt = stmt.order_by(Notification.created_at.desc())
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0
    stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
    rows = list((await db.execute(stmt)).scalars().all())
    return Page.of(rows, total, params.page, params.size)


async def create_notification(
    db: AsyncSession, tenant_id: int, user_id: int | None, channel: str,
    template: str, title: str, body: str,
) -> Notification:
    notif = Notification(
        tenant_id=tenant_id, user_id=user_id, channel=channel,
        template=template, title=title, body=body, status="pending",
    )
    db.add(notif)
    await db.flush()
    return notif


async def mark_notification_sent(db: AsyncSession, notif_id: int) -> Notification:
    n = await db.get(Notification, notif_id)
    if n is None:
        raise RuntimeError("notification not found")
    n.status = "sent"
    n.sent_at = utcnow()
    await db.flush()
    return n


# ----------------------------- 导出任务（mock，不生成真实文件） -----------------------------

class MockExportTask:
    def __init__(self, id, tenant_id, resource, fmt, status, created_by, created_at):
        self.id = id
        self.tenant_id = tenant_id
        self.resource = resource
        self.format = fmt
        self.status = status
        self.file_path = f"/tmp/export/{tenant_id}_{resource}_{id}.{fmt}" if status == "completed" else None
        self.created_by = created_by
        self.created_at = created_at


_EXPORT_DB: list[MockExportTask] = []


async def create_export(db: AsyncSession, tenant_id: int, user_id: int, payload: ExportTaskCreate) -> MockExportTask:
    global _EXPORT_DB
    tid = len(_EXPORT_DB) + 1
    # mock 立即完成
    task = MockExportTask(tid, tenant_id, payload.resource, payload.format, "completed", user_id, utcnow())
    _EXPORT_DB.append(task)
    return task


async def list_exports(tenant_id: int) -> list[MockExportTask]:
    return [t for t in _EXPORT_DB if t.tenant_id == tenant_id]


def reset_export_db():
    global _EXPORT_DB
    _EXPORT_DB = []
