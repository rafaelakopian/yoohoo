"""Demo tuition billing: plans, student billing, and invoice generation."""

import calendar
import sys
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.school.billing.models import (
    BillingFrequency,
    StudentBilling,
    TuitionPlan,
)
from app.modules.products.school.billing.service import TuitionBillingService
from app.modules.products.school.student.models import Student


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


async def create_demo_billing(
    db: AsyncSession,
    tenant_slug: str,
    students: list[Student],
    users: dict,
) -> None:
    """Create tuition plan, student billing records, and generate last month's invoices."""
    # 1. Tuition plan
    plan = TuitionPlan(
        name="Standaard lestarieven",
        description="Maandelijks lesgeld",
        amount_cents=8500,  # EUR 85,00 per maand
        currency="EUR",
        frequency=BillingFrequency.monthly,
        is_active=True,
    )
    db.add(plan)
    await db.flush()

    # 2. Student billing (link each student to the plan)
    ouder1 = users.get("ouder1")
    ouder2 = users.get("ouder2")
    billing_ids = []

    for i, student in enumerate(students):
        # Alternate payer between ouder1 and ouder2
        payer = ouder1 if (i % 2 == 0) else ouder2
        payer_name = payer.full_name if payer else "Onbekend"
        payer_email = payer.email if payer else "onbekend@demo.yoohoo"

        sb = StudentBilling(
            student_id=student.id,
            tuition_plan_id=plan.id,
            payer_user_id=payer.id if payer else None,
            payer_name=payer_name,
            payer_email=payer_email,
            status="active",
        )
        db.add(sb)
        await db.flush()
        billing_ids.append(sb.id)

    _log(f"    {len(billing_ids)} student-billing records aangemaakt")

    # 3. Generate invoices for last month
    now = datetime.now(timezone.utc)
    if now.month == 1:
        last_month, year = 12, now.year - 1
    else:
        last_month, year = now.month - 1, now.year

    _, last_day = calendar.monthrange(year, last_month)
    period_start = datetime(year, last_month, 1, tzinfo=timezone.utc)
    period_end = datetime(year, last_month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    svc = TuitionBillingService(db)
    invoices = await svc.generate_invoices(
        period_start=period_start,
        period_end=period_end,
        tenant_slug=tenant_slug,
    )
    await db.flush()
    _log(f"    {len(invoices)} facturen gegenereerd (periode {last_month}/{year})")
