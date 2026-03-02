"""Tuition billing API: plans, student billing, invoices."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_tenant_db
from app.modules.platform.auth.dependencies import (
    get_current_user,
    is_data_restricted,
    require_any_permission,
    require_permission,
)
from app.modules.platform.auth.models import User
from app.modules.tenant.billing.schemas import (
    InvoiceGenerateRequest,
    StudentBillingCreate,
    StudentBillingResponse,
    StudentBillingUpdate,
    TuitionInvoiceListResponse,
    TuitionInvoiceResponse,
    TuitionPlanCreate,
    TuitionPlanResponse,
    TuitionPlanUpdate,
)
from app.modules.tenant.billing.service import TuitionBillingService

router = APIRouter(prefix="/tuition", tags=["tuition-billing"])


async def get_tuition_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> TuitionBillingService:
    return TuitionBillingService(db)


# ─── Tuition Plans ───


@router.get("/plans", response_model=list[TuitionPlanResponse])
async def list_plans(
    active_only: bool = Query(True),
    _: User = Depends(require_permission("billing.view")),
    service: TuitionBillingService = Depends(get_tuition_service),
):
    """List tuition plans for this school."""
    return await service.list_plans(active_only=active_only)


@router.post("/plans", response_model=TuitionPlanResponse, status_code=201)
async def create_plan(
    data: TuitionPlanCreate,
    _: User = Depends(require_permission("billing.manage")),
    service: TuitionBillingService = Depends(get_tuition_service),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a tuition plan."""
    result = await service.create_plan(data.model_dump())
    await db.commit()
    return result


@router.put("/plans/{plan_id}", response_model=TuitionPlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    data: TuitionPlanUpdate,
    _: User = Depends(require_permission("billing.manage")),
    service: TuitionBillingService = Depends(get_tuition_service),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a tuition plan."""
    result = await service.update_plan(plan_id, data.model_dump(exclude_unset=True))
    await db.commit()
    return result


@router.delete("/plans/{plan_id}", response_model=TuitionPlanResponse)
async def deactivate_plan(
    plan_id: uuid.UUID,
    _: User = Depends(require_permission("billing.manage")),
    service: TuitionBillingService = Depends(get_tuition_service),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Deactivate a tuition plan (soft delete)."""
    result = await service.deactivate_plan(plan_id)
    await db.commit()
    return result


# ─── Student Billing ───


@router.get("/student-billing", response_model=list[StudentBillingResponse])
async def list_student_billing(
    student_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(require_any_permission("billing.view", "billing.view_own")),
    service: TuitionBillingService = Depends(get_tuition_service),
):
    """List student billing configurations."""
    items, _ = await service.list_student_billing(student_id, skip, limit)
    return items


@router.get(
    "/student-billing/{student_id}", response_model=StudentBillingResponse | None
)
async def get_student_billing(
    student_id: uuid.UUID,
    _: User = Depends(require_any_permission("billing.view", "billing.view_own")),
    service: TuitionBillingService = Depends(get_tuition_service),
):
    """Get billing configuration for a specific student."""
    return await service.get_student_billing(student_id)


@router.post(
    "/student-billing", response_model=StudentBillingResponse, status_code=201
)
async def create_student_billing(
    data: StudentBillingCreate,
    _: User = Depends(require_permission("billing.manage")),
    service: TuitionBillingService = Depends(get_tuition_service),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Assign billing to a student."""
    result = await service.create_student_billing(data.model_dump())
    await db.commit()
    return result


@router.put(
    "/student-billing/{billing_id}", response_model=StudentBillingResponse
)
async def update_student_billing(
    billing_id: uuid.UUID,
    data: StudentBillingUpdate,
    _: User = Depends(require_permission("billing.manage")),
    service: TuitionBillingService = Depends(get_tuition_service),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update student billing configuration."""
    result = await service.update_student_billing(
        billing_id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    return result


# ─── Tuition Invoices ───


@router.get("/invoices", response_model=TuitionInvoiceListResponse)
async def list_invoices(
    student_billing_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(require_any_permission("billing.view", "billing.view_own")),
    service: TuitionBillingService = Depends(get_tuition_service),
):
    """List tuition invoices."""
    items, total = await service.list_invoices(student_billing_id, status, skip, limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/invoices/generate", response_model=list[TuitionInvoiceResponse])
async def generate_invoices(
    data: InvoiceGenerateRequest,
    request: Request,
    _: User = Depends(require_permission("billing.manage")),
    service: TuitionBillingService = Depends(get_tuition_service),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Generate invoices for a billing period."""
    tenant_slug = getattr(request.state, "tenant_slug", "unknown")
    result = await service.generate_invoices(
        data.period_start, data.period_end, tenant_slug, data.student_billing_ids
    )
    await db.commit()
    return result


@router.post("/invoices/{invoice_id}/send", response_model=TuitionInvoiceResponse)
async def send_invoice(
    invoice_id: uuid.UUID,
    _: User = Depends(require_permission("billing.manage")),
    service: TuitionBillingService = Depends(get_tuition_service),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Send an invoice (mark as sent, trigger email notification)."""
    result = await service.send_invoice(invoice_id)
    await db.commit()
    return result


@router.get("/invoices/{invoice_id}", response_model=TuitionInvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    _: User = Depends(require_any_permission("billing.view", "billing.view_own")),
    service: TuitionBillingService = Depends(get_tuition_service),
):
    """Get a single tuition invoice."""
    return await service.get_invoice(invoice_id)
