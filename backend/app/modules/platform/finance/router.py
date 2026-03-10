"""Finance dashboard API endpoints."""

import csv
import io
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.dependencies import get_arq
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.finance.schemas import (
    DunningCandidate,
    DunningSendResult,
    OutstandingPayments,
    RevenueOverview,
    TaxReport,
)
from app.modules.platform.finance.service import FinanceService

router = APIRouter(prefix="/platform/finance", tags=["finance"])


def _get_service(db: AsyncSession = Depends(get_central_db)) -> FinanceService:
    return FinanceService(db)


@router.get("/overview", response_model=RevenueOverview)
async def get_revenue_overview(
    current_user: User = Depends(require_permission("finance.view_dashboard")),
    service: FinanceService = Depends(_get_service),
):
    return await service.get_revenue_overview()


@router.get("/outstanding", response_model=OutstandingPayments)
async def get_outstanding_payments(
    current_user: User = Depends(require_permission("finance.view_dashboard")),
    service: FinanceService = Depends(_get_service),
):
    return await service.get_outstanding_payments()


@router.get("/tax-report", response_model=TaxReport)
async def get_tax_report(
    year: int = Query(..., ge=2020, le=2100),
    quarter: int = Query(..., ge=1, le=4),
    current_user: User = Depends(require_permission("finance.view_dashboard")),
    service: FinanceService = Depends(_get_service),
):
    return await service.get_tax_report(year, quarter)


@router.get("/tax-report/export")
async def export_tax_report(
    year: int = Query(..., ge=2020, le=2100),
    quarter: int = Query(..., ge=1, le=4),
    current_user: User = Depends(require_permission("finance.export_reports")),
    service: FinanceService = Depends(_get_service),
):
    report = await service.get_tax_report(year, quarter)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Maand", "Facturen", "Excl. BTW (€)", "BTW (€)", "Incl. BTW (€)"])

    for line in report.lines:
        writer.writerow([
            line.month,
            line.invoice_count,
            f"{line.subtotal_cents / 100:.2f}",
            f"{line.tax_cents / 100:.2f}",
            f"{line.total_cents / 100:.2f}",
        ])
    writer.writerow([
        "Totaal",
        report.totals.invoice_count,
        f"{report.totals.subtotal_cents / 100:.2f}",
        f"{report.totals.tax_cents / 100:.2f}",
        f"{report.totals.total_cents / 100:.2f}",
    ])

    filename = f"btw-rapport-{year}-Q{quarter}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/dunning/candidates", response_model=list[DunningCandidate])
async def get_dunning_candidates(
    current_user: User = Depends(require_permission("finance.manage_dunning")),
    service: FinanceService = Depends(_get_service),
):
    return await service.get_dunning_candidates()


@router.post("/dunning/send", response_model=DunningSendResult)
async def trigger_dunning(
    tenant_id: uuid.UUID | None = Query(None),
    invoice_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(require_permission("finance.manage_dunning")),
    service: FinanceService = Depends(_get_service),
    arq_pool=Depends(get_arq),
):
    sent, skipped = await service.send_dunning_reminders(
        arq_pool, tenant_id=tenant_id, invoice_id=invoice_id,
    )
    return DunningSendResult(sent=sent, skipped=skipped)
