"""Platform billing API: plans, subscriptions, providers, invoices, payments."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.billing.schemas import (
    InvoiceListResponse,
    InvoiceResponse,
    PaymentListResponse,
    PaymentResponse,
    PlatformPlanCreate,
    PlatformPlanResponse,
    PlatformPlanUpdate,
    ProviderConfigCreate,
    ProviderConfigResponse,
    ProviderConfigUpdate,
    RefundRequest,
    ResumeSubscriptionRequest,
    ResumeSubscriptionResponse,
    SubscriptionCreate,
    SubscriptionOverviewResponse,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from app.modules.platform.billing.service import BillingService

router = APIRouter(prefix="/platform/billing", tags=["platform-billing"])


async def get_billing_service(
    db: AsyncSession = Depends(get_central_db),
) -> BillingService:
    return BillingService(db)


# ─── Platform Plans (public read, superadmin write) ───


@router.get("/plans", response_model=list[PlatformPlanResponse])
async def list_plans(
    active_only: bool = Query(True),
    service: BillingService = Depends(get_billing_service),
):
    """List platform plans. Public endpoint for pricing page."""
    return await service.list_plans(active_only=active_only)


@router.post("/plans", response_model=PlatformPlanResponse, status_code=201)
async def create_plan(
    data: PlatformPlanCreate,
    _: User = Depends(require_permission("platform.manage_orgs")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Create a new platform plan. Superadmin only."""
    result = await service.create_plan(data.model_dump())
    await db.commit()
    return result


@router.put("/plans/{plan_id}", response_model=PlatformPlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    data: PlatformPlanUpdate,
    _: User = Depends(require_permission("platform.manage_orgs")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Update a platform plan. Superadmin only."""
    result = await service.update_plan(plan_id, data.model_dump(exclude_unset=True))
    await db.commit()
    return result


# ─── Subscriptions (superadmin) ───


@router.get("/subscriptions", response_model=SubscriptionOverviewResponse)
async def list_subscriptions_overview(
    status: str | None = Query(None),
    plan_id: uuid.UUID | None = Query(None),
    sort_by: str = Query("tenant"),
    sort_dir: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: User = Depends(require_permission("billing.view")),
    service: BillingService = Depends(get_billing_service),
):
    """List all subscriptions with overview data."""
    return await service.list_subscriptions_overview(
        status=status,
        plan_id=plan_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/subscriptions/{tenant_id}", response_model=SubscriptionResponse | None
)
async def get_subscription(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("billing.view")),
    service: BillingService = Depends(get_billing_service),
):
    """Get a tenant's subscription."""
    return await service.get_subscription(tenant_id)


@router.post(
    "/subscriptions/{tenant_id}",
    response_model=SubscriptionResponse,
    status_code=201,
)
async def create_subscription(
    tenant_id: uuid.UUID,
    data: SubscriptionCreate,
    _: User = Depends(require_permission("platform.manage_orgs")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Create a subscription for a tenant. Superadmin only."""
    result = await service.create_subscription(tenant_id, data.model_dump())
    await db.commit()
    return result


@router.put("/subscriptions/{tenant_id}", response_model=SubscriptionResponse)
async def update_subscription(
    tenant_id: uuid.UUID,
    data: SubscriptionUpdate,
    _: User = Depends(require_permission("platform.manage_orgs")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Update a tenant's subscription. Superadmin only."""
    result = await service.update_subscription(tenant_id, data.model_dump(exclude_unset=True))
    await db.commit()
    return result


@router.post(
    "/subscriptions/{tenant_id}/cancel", response_model=SubscriptionResponse
)
async def cancel_subscription(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_orgs")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Cancel a tenant's subscription. Superadmin only."""
    result = await service.cancel_subscription(tenant_id)
    await db.commit()
    return result


@router.post(
    "/subscriptions/{tenant_id}/pause", response_model=SubscriptionResponse
)
async def pause_subscription(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_orgs")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Pause a tenant's subscription. Superadmin only."""
    result = await service.pause_subscription(tenant_id)
    await db.commit()
    return result


@router.post(
    "/subscriptions/{tenant_id}/resume", response_model=ResumeSubscriptionResponse
)
async def resume_subscription(
    tenant_id: uuid.UUID,
    data: ResumeSubscriptionRequest,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Resume a paused subscription with invoice choice. Superadmin only."""
    from app.modules.platform.billing.service import ResumeMode

    result = await service.resume_subscription(
        tenant_id=tenant_id,
        resume_mode=ResumeMode(data.resume_mode),
        actor_id=current_user.id,
    )
    await db.commit()
    return result


# ─── Provider Configuration ───


@router.get(
    "/providers/{tenant_id}", response_model=list[ProviderConfigResponse]
)
async def get_providers(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("billing.manage_provider")),
    service: BillingService = Depends(get_billing_service),
):
    """Get payment provider configurations for a tenant."""
    return await service.get_providers(tenant_id)


@router.post(
    "/providers/{tenant_id}",
    response_model=ProviderConfigResponse,
    status_code=201,
)
async def configure_provider(
    tenant_id: uuid.UUID,
    data: ProviderConfigCreate,
    _: User = Depends(require_permission("billing.manage_provider")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Configure a payment provider for a tenant."""
    result = await service.configure_provider(tenant_id, data.model_dump())
    await db.commit()
    return result


@router.put(
    "/providers/{tenant_id}/{provider_id}",
    response_model=ProviderConfigResponse,
)
async def update_provider(
    tenant_id: uuid.UUID,
    provider_id: uuid.UUID,
    data: ProviderConfigUpdate,
    _: User = Depends(require_permission("billing.manage_provider")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Update a payment provider configuration."""
    result = await service.update_provider(
        tenant_id, provider_id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    return result


# ─── Invoices ───


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    tenant_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    invoice_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(require_permission("billing.view")),
    service: BillingService = Depends(get_billing_service),
):
    """List invoices with optional filters."""
    items, total = await service.list_invoices(tenant_id, status, skip, limit, invoice_type=invoice_type)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    _: User = Depends(require_permission("billing.view")),
    service: BillingService = Depends(get_billing_service),
):
    """Get a single invoice."""
    return await service.get_invoice(invoice_id)


@router.post("/invoices/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_paid(
    invoice_id: uuid.UUID,
    _: User = Depends(require_permission("billing.manage")),
    service: BillingService = Depends(get_billing_service),
):
    """Manually mark an open/overdue invoice as paid."""
    return await service.mark_invoice_paid(invoice_id)


# ─── Payments ───


@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    tenant_id: uuid.UUID | None = Query(None),
    invoice_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(require_permission("billing.view")),
    service: BillingService = Depends(get_billing_service),
):
    """List payments with optional filters."""
    items, total = await service.list_payments(tenant_id, invoice_id, skip, limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/payments/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: uuid.UUID,
    data: RefundRequest,
    _: User = Depends(require_permission("billing.refund")),
    service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Create a refund for a payment."""
    result = await service.create_refund(
        payment_id, data.amount_cents, data.description
    )
    await db.commit()
    return result
