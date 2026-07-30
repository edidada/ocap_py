"""BP-D 处置执行域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tenant_id, require_permission
from app.db.session import get_db
from app.domains.iam.models import User
from app.domains.action import service
from app.domains.action.schemas import (
    ActionCreate,
    ActionOut,
    ActionUpdate,
    BatchDispositionRequest,
    ClosureRequest,
    ExecutionOut,
    SlaBreach,
    SlaCreate,
    SlaOut,
    SignatureOut,
    SignRequest,
)

router = APIRouter(prefix="/actions", tags=["actions"])


@router.post("", response_model=ActionOut, status_code=status.HTTP_201_CREATED)
async def create_action(
    payload: ActionCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:action:create")),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    action = await service.create_action(db, tenant_id, payload)
    await db.commit()
    return service.action_to_out(action)


@router.get("", response_model=list[ActionOut])
async def list_actions(
    event_id: int | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_actions(db, tenant_id, event_id=event_id, status=status, page=page, size=size)
    return result.items


@router.get("/{action_id}", response_model=ActionOut)
async def get_action(
    action_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    action = await service.get_action(db, tenant_id, action_id)
    return service.action_to_out(action)


@router.patch("/{action_id}", response_model=ActionOut)
async def update_action(
    action_id: int,
    payload: ActionUpdate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:action:create")),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    action = await service.update_action(db, tenant_id, action_id, payload)
    await db.commit()
    return service.action_to_out(action)


@router.post("/{action_id}/execute", response_model=ExecutionOut)
async def execute_action(
    action_id: int,
    payload: dict | None = None,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:action:execute")),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    detail = (payload or {}).get("detail", "")
    execution = await service.execute_action(db, tenant_id, action_id, user.id, detail)
    await db.commit()
    return ExecutionOut.model_validate(execution)


@router.post("/{action_id}/rollback", response_model=ActionOut)
async def rollback_action(
    action_id: int,
    payload: dict | None = None,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:action:rollback")),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    reason = (payload or {}).get("reason", "")
    action = await service.rollback_action(db, tenant_id, action_id, user.id, reason)
    await db.commit()
    return service.action_to_out(action)


# ----- 电子签核 -----


@router.post("/{action_id}/signatures", response_model=SignatureOut, status_code=status.HTTP_201_CREATED)
async def sign_action(
    action_id: int,
    payload: SignRequest,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:action:sign")),
    db: AsyncSession = Depends(get_db),
) -> SignatureOut:
    sig = await service.sign_action(db, tenant_id, action_id, user.id, payload)
    await db.commit()
    return SignatureOut.model_validate(sig)


@router.get("/{action_id}/signatures", response_model=list[SignatureOut])
async def list_signatures(
    action_id: int,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sigs = await service.list_signatures(db, tenant_id, action_id)
    return [SignatureOut.model_validate(s) for s in sigs]


# ----- SLA -----


@router.post("/slas", response_model=SlaOut, status_code=status.HTTP_201_CREATED)
async def create_sla(
    payload: SlaCreate,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:config:write")),
    db: AsyncSession = Depends(get_db),
) -> SlaOut:
    sla = await service.create_sla(db, tenant_id, payload)
    await db.commit()
    return service.sla_to_out(sla)


@router.get("/slas", response_model=list[SlaOut])
async def list_slas(
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    slas = await service.list_slas(db, tenant_id)
    return [service.sla_to_out(s) for s in slas]


@router.get("/slas/breaches", response_model=list[SlaBreach])
async def sla_breaches(
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:action:execute")),
    db: AsyncSession = Depends(get_db),
):
    return await service.check_sla_breaches(db, tenant_id)


# ----- 批次处置 -----


@router.post("/{action_id}/batch-dispositions", status_code=status.HTTP_201_CREATED)
async def dispose_batch(
    action_id: int,
    payload: BatchDispositionRequest,
    tenant_id: int = Depends(get_tenant_id),
    _: User = Depends(require_permission("ocap:action:execute")),
    db: AsyncSession = Depends(get_db),
):
    from app.integrations.registry import get_integration_registry

    reg = get_integration_registry()
    mes_client = reg.get("mes")
    rec = await service.dispose_batch(db, tenant_id, action_id, payload, mes_client)
    await db.commit()
    return {
        "id": rec.id,
        "action_id": rec.action_id,
        "batch_id": rec.batch_id,
        "disposition": rec.disposition,
        "synced": rec.synced,
    }


# ----- 闭环验证 -----


@router.post("/{action_id}/closure", status_code=status.HTTP_201_CREATED)
async def validate_closure(
    action_id: int,
    payload: ClosureRequest,
    tenant_id: int = Depends(get_tenant_id),
    user: User = Depends(require_permission("ocap:action:sign")),
    db: AsyncSession = Depends(get_db),
):
    cv = await service.validate_closure(db, tenant_id, action_id, user.id, payload)
    await db.commit()
    return {
        "id": cv.id,
        "action_id": cv.action_id,
        "validator_id": cv.validator_id,
        "passed": cv.passed,
        "note": cv.note,
    }
