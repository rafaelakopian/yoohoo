"""Tenant-scoped billing endpoints: pay invoices, view platform invoices.

Mounted under /org/{slug}/billing/ (tenant context required).
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.billing.schemas import InvoiceResponse
from app.modules.platform.billing.service import BillingService

router = APIRouter(prefix="/billing", tags=["tenant-billing"])


async def _get_billing_service(
    db: AsyncSession = Depends(get_central_db),
) -> BillingService:
    return BillingService(db)


class PayInvoiceResponse(BaseModel):
    payment_id: uuid.UUID
    checkout_url: str | None
    invoice_number: str


@router.post(
    "/invoices/{invoice_id}/pay",
    response_model=PayInvoiceResponse,
)
async def pay_invoice(
    invoice_id: uuid.UUID,
    request: Request,
    _user: User = Depends(get_current_user),
    service: BillingService = Depends(_get_billing_service),
    db: AsyncSession = Depends(get_central_db),
):
    """Create a payment link for an open/overdue platform invoice.

    Any authenticated tenant member can initiate payment.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    tenant_slug = getattr(request.state, "tenant_slug", "")

    result = await service.create_invoice_payment(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        tenant_slug=tenant_slug,
    )
    await db.commit()
    return result


@router.get(
    "/platform-invoices",
    response_model=list[InvoiceResponse],
)
async def list_platform_invoices(
    request: Request,
    status: str | None = Query(None, description="Kommagescheiden statussen, bijv. 'open,overdue'"),
    _user: User = Depends(get_current_user),
    service: BillingService = Depends(_get_billing_service),
):
    """List platform invoices for the current tenant.

    Any authenticated tenant member can view platform invoices.
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    statuses = [s.strip() for s in status.split(",") if s.strip()] if status else None

    return await service.list_platform_invoices_for_tenant(
        tenant_id=tenant_id,
        statuses=statuses,
    )
