"""Lightweight subscription status endpoint for tenant context.

Mounted under /org/{slug}/subscription-status (tenant-scoped).
Used by the frontend to check subscription status without loading full billing data.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.billing.models import PlatformSubscription

logger = structlog.get_logger()

router = APIRouter(tags=["subscription-status"])


class SubscriptionStatusResponse(BaseModel):
    status: str  # active/trialing/paused/cancelled/expired/none
    plan_name: str | None = None
    paused_at: datetime | None = None
    cancelled_at: datetime | None = None


@router.get("/subscription-status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    request: Request,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    """Get the subscription status for the current tenant."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context vereist")

    result = await db.execute(
        select(PlatformSubscription)
        .options(selectinload(PlatformSubscription.plan))
        .where(PlatformSubscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        return SubscriptionStatusResponse(status="none")

    status = sub.status.value if hasattr(sub.status, "value") else sub.status
    plan_name = sub.plan.name if sub.plan else None

    return SubscriptionStatusResponse(
        status=status,
        plan_name=plan_name,
        paused_at=sub.cancelled_at if status == "paused" else None,
        cancelled_at=sub.cancelled_at,
    )
