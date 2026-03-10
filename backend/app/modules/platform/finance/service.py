"""Finance service — revenue, outstanding payments, tax reports, dunning."""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.finance.schemas import (
    DunningCandidate,
    InvoiceAging,
    OutstandingPayments,
    RevenueOverview,
    TaxReport,
    TaxReportLine,
    TenantRevenue,
)
from app.modules.platform.tenant_mgmt.models import Tenant

logger = structlog.get_logger()


class FinanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_revenue_overview(self) -> RevenueOverview:
        now = datetime.now(timezone.utc)

        # --- MRR: active subscriptions joined to plans ---
        mrr_query = (
            select(
                PlatformSubscription.tenant_id,
                PlatformPlan.price_cents,
                PlatformPlan.interval,
            )
            .join(PlatformPlan, PlatformSubscription.plan_id == PlatformPlan.id)
            .where(PlatformSubscription.status == SubscriptionStatus.active)
        )
        result = await self.db.execute(mrr_query)
        rows = result.all()

        mrr_cents = 0
        tenant_mrr: dict[uuid.UUID, int] = {}
        for tenant_id, price_cents, interval in rows:
            monthly = price_cents if interval.value == "monthly" else price_cents // 12
            mrr_cents += monthly
            tenant_mrr[tenant_id] = monthly

        arr_cents = mrr_cents * 12

        # --- Growth % vs previous month ---
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        first_of_prev_month = (first_of_this_month - timedelta(days=1)).replace(day=1)

        new_this_month = await self.db.scalar(
            select(func.count())
            .select_from(PlatformSubscription)
            .where(
                PlatformSubscription.created_at >= first_of_this_month,
                PlatformSubscription.status.in_([
                    SubscriptionStatus.active, SubscriptionStatus.trialing
                ]),
            )
        ) or 0

        new_prev_month = await self.db.scalar(
            select(func.count())
            .select_from(PlatformSubscription)
            .where(
                PlatformSubscription.created_at >= first_of_prev_month,
                PlatformSubscription.created_at < first_of_this_month,
                PlatformSubscription.status.in_([
                    SubscriptionStatus.active, SubscriptionStatus.trialing
                ]),
            )
        ) or 0

        growth_percent = None
        if new_prev_month > 0:
            growth_percent = round(((new_this_month - new_prev_month) / new_prev_month) * 100, 1)

        # --- Total revenue (all-time paid platform invoices) ---
        total_revenue_cents = await self.db.scalar(
            select(func.coalesce(func.sum(Invoice.total_cents), 0))
            .where(
                Invoice.status == InvoiceStatus.paid,
                Invoice.invoice_type == InvoiceType.platform,
            )
        ) or 0

        # --- Lifetime value per tenant (top 10, platform invoices only) ---
        ltv_query = (
            select(
                Invoice.tenant_id,
                func.sum(Invoice.total_cents).label("ltv"),
            )
            .where(
                Invoice.status == InvoiceStatus.paid,
                Invoice.invoice_type == InvoiceType.platform,
            )
            .group_by(Invoice.tenant_id)
            .order_by(func.sum(Invoice.total_cents).desc())
            .limit(10)
        )
        ltv_result = await self.db.execute(ltv_query)
        ltv_rows = ltv_result.all()

        # Fetch tenant info for top tenants
        tenant_ids = [r.tenant_id for r in ltv_rows]
        tenants_map: dict[uuid.UUID, Tenant] = {}
        if tenant_ids:
            tenants_result = await self.db.execute(
                select(Tenant).where(Tenant.id.in_(tenant_ids))
            )
            for t in tenants_result.scalars():
                tenants_map[t.id] = t

        # Subscription status per tenant
        sub_status_query = (
            select(PlatformSubscription.tenant_id, PlatformSubscription.status)
            .where(PlatformSubscription.tenant_id.in_(tenant_ids))
        )
        sub_result = await self.db.execute(sub_status_query)
        sub_status_map = {r.tenant_id: r.status.value for r in sub_result.all()}

        top_tenants = []
        for row in ltv_rows:
            tenant = tenants_map.get(row.tenant_id)
            if not tenant:
                continue
            top_tenants.append(TenantRevenue(
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                tenant_slug=tenant.slug,
                lifetime_value_cents=row.ltv,
                mrr_cents=tenant_mrr.get(tenant.id, 0),
                subscription_status=sub_status_map.get(tenant.id),
                since=tenant.created_at,
            ))

        # --- Subscription status counts ---
        status_query = (
            select(
                PlatformSubscription.status,
                func.count().label("cnt"),
            )
            .group_by(PlatformSubscription.status)
        )
        status_result = await self.db.execute(status_query)
        subscription_counts = {r.status.value: r.cnt for r in status_result.all()}
        # Ensure all statuses present
        for s in SubscriptionStatus:
            subscription_counts.setdefault(s.value, 0)

        # --- Funnel ---
        registered = await self.db.scalar(
            select(func.count()).select_from(Tenant)
        ) or 0
        provisioned = await self.db.scalar(
            select(func.count()).select_from(Tenant).where(Tenant.is_provisioned.is_(True))
        ) or 0
        active_sub = await self.db.scalar(
            select(func.count(func.distinct(PlatformSubscription.tenant_id)))
            .where(PlatformSubscription.status == SubscriptionStatus.active)
        ) or 0
        paying = await self.db.scalar(
            select(func.count(func.distinct(Invoice.tenant_id)))
            .where(
                Invoice.status == InvoiceStatus.paid,
                Invoice.invoice_type == InvoiceType.platform,
            )
        ) or 0

        return RevenueOverview(
            mrr_cents=mrr_cents,
            arr_cents=arr_cents,
            growth_percent=growth_percent,
            total_revenue_cents=total_revenue_cents,
            top_tenants=top_tenants,
            subscription_counts=subscription_counts,
            funnel={
                "registered": registered,
                "provisioned": provisioned,
                "active_subscription": active_sub,
                "paying": paying,
            },
            generated_at=now,
        )

    async def get_outstanding_payments(self) -> OutstandingPayments:
        now = datetime.now(timezone.utc)

        # All open/overdue platform invoices
        query = (
            select(Invoice, Tenant.name)
            .join(Tenant, Invoice.tenant_id == Tenant.id)
            .where(
                Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.overdue]),
                Invoice.invoice_type == InvoiceType.platform,
                Invoice.due_date.isnot(None),
            )
        )
        result = await self.db.execute(query)
        rows = result.all()

        buckets_data: dict[str, dict] = {
            "current": {"days_range": "0-30", "count": 0, "total_cents": 0, "tenants": []},
            "late": {"days_range": "31-60", "count": 0, "total_cents": 0, "tenants": []},
            "very_late": {"days_range": "61-90", "count": 0, "total_cents": 0, "tenants": []},
            "critical": {"days_range": "90+", "count": 0, "total_cents": 0, "tenants": []},
        }

        total_outstanding = 0
        for invoice, tenant_name in rows:
            days_overdue = max(0, (now - invoice.due_date).days)
            total_outstanding += invoice.total_cents

            if days_overdue <= 30:
                bucket = "current"
            elif days_overdue <= 60:
                bucket = "late"
            elif days_overdue <= 90:
                bucket = "very_late"
            else:
                bucket = "critical"

            buckets_data[bucket]["count"] += 1
            buckets_data[bucket]["total_cents"] += invoice.total_cents
            if tenant_name not in buckets_data[bucket]["tenants"]:
                buckets_data[bucket]["tenants"].append(tenant_name)

        buckets = [
            InvoiceAging(bucket=key, **data)
            for key, data in buckets_data.items()
        ]

        return OutstandingPayments(
            total_outstanding_cents=total_outstanding,
            buckets=buckets,
            generated_at=now,
        )

    async def get_tax_report(self, year: int, quarter: int) -> TaxReport:
        # Quarter boundaries
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime(year, start_month, 1, tzinfo=timezone.utc)
        if quarter == 4:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, start_month + 3, 1, tzinfo=timezone.utc)

        # Only platform invoices that are paid (Yoohoo's own revenue)
        query = (
            select(Invoice)
            .where(
                Invoice.invoice_type == InvoiceType.platform,
                Invoice.status == InvoiceStatus.paid,
                Invoice.paid_at >= start_date,
                Invoice.paid_at < end_date,
            )
            .order_by(Invoice.paid_at)
        )
        result = await self.db.execute(query)
        invoices = result.scalars().all()

        # Group by month
        monthly: dict[str, dict] = defaultdict(
            lambda: {"invoice_count": 0, "subtotal_cents": 0, "tax_cents": 0, "total_cents": 0}
        )
        for inv in invoices:
            month_key = inv.paid_at.strftime("%Y-%m")
            monthly[month_key]["invoice_count"] += 1
            monthly[month_key]["subtotal_cents"] += inv.subtotal_cents
            monthly[month_key]["tax_cents"] += inv.tax_cents
            monthly[month_key]["total_cents"] += inv.total_cents

        # Build lines for all months in quarter
        lines = []
        for m in range(start_month, start_month + 3):
            month_key = f"{year}-{m:02d}"
            data = monthly.get(month_key, {"invoice_count": 0, "subtotal_cents": 0, "tax_cents": 0, "total_cents": 0})
            lines.append(TaxReportLine(month=month_key, **data))

        totals = TaxReportLine(
            month="totaal",
            invoice_count=sum(l.invoice_count for l in lines),
            subtotal_cents=sum(l.subtotal_cents for l in lines),
            tax_cents=sum(l.tax_cents for l in lines),
            total_cents=sum(l.total_cents for l in lines),
        )

        return TaxReport(
            year=year,
            quarter=quarter,
            lines=lines,
            totals=totals,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_dunning_candidates(self) -> list[DunningCandidate]:
        now = datetime.now(timezone.utc)
        threshold_days = settings.billing_dunning_first_reminder_days

        # Overdue platform invoices past the threshold
        query = (
            select(Invoice, Tenant.name)
            .join(Tenant, Invoice.tenant_id == Tenant.id)
            .where(
                Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.overdue]),
                Invoice.invoice_type == InvoiceType.platform,
                Invoice.due_date.isnot(None),
                Invoice.due_date <= now - timedelta(days=threshold_days),
            )
            .order_by(Invoice.due_date)
        )
        result = await self.db.execute(query)
        rows = result.all()

        candidates = []
        for invoice, tenant_name in rows:
            # Check reminder history from extra_data
            extra = invoice.extra_data or {}
            reminder_count = extra.get("dunning_reminder_count", 0)
            last_sent_str = extra.get("dunning_last_sent_at")
            last_sent = datetime.fromisoformat(last_sent_str) if last_sent_str else None

            # Skip if already reminded today
            if last_sent and last_sent.date() >= now.date():
                continue

            days_overdue = (now - invoice.due_date).days

            # Determine which round applies
            if reminder_count == 0 and days_overdue >= threshold_days:
                pass  # First reminder
            elif reminder_count == 1 and days_overdue >= settings.billing_dunning_second_reminder_days:
                pass  # Second reminder
            elif reminder_count == 2 and days_overdue >= settings.billing_dunning_third_reminder_days:
                pass  # Third reminder
            elif reminder_count >= 3:
                continue  # Already sent all reminders
            else:
                continue  # Not yet time for next reminder

            candidates.append(DunningCandidate(
                tenant_id=invoice.tenant_id,
                tenant_name=tenant_name,
                contact_email=invoice.recipient_email,
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                amount_cents=invoice.total_cents,
                days_overdue=days_overdue,
                reminder_count=reminder_count,
                last_reminder_sent_at=last_sent,
            ))

        return candidates

    async def send_dunning_reminders(
        self,
        arq_pool,
        *,
        tenant_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
    ) -> tuple[int, int]:
        """Send dunning reminders. Returns (sent, skipped)."""
        candidates = await self.get_dunning_candidates()

        # Filter if specific target given
        if tenant_id:
            candidates = [c for c in candidates if c.tenant_id == tenant_id]
        if invoice_id:
            candidates = [c for c in candidates if c.invoice_id == invoice_id]

        sent = 0
        skipped = 0
        now = datetime.now(timezone.utc)

        for candidate in candidates:
            new_count = candidate.reminder_count + 1

            # Build email
            subject = f"Betalingsherinnering ({new_count}e) — factuur {candidate.invoice_number}"
            body = _render_dunning_email(
                tenant_name=candidate.tenant_name,
                invoice_number=candidate.invoice_number,
                amount_cents=candidate.amount_cents,
                days_overdue=candidate.days_overdue,
                reminder_round=new_count,
            )

            # Enqueue email
            if arq_pool:
                try:
                    await arq_pool.enqueue_job(
                        "send_email_job",
                        to=candidate.contact_email,
                        subject=subject,
                        html_body=body,
                    )
                except Exception:
                    logger.warning("dunning.enqueue_failed", invoice_id=str(candidate.invoice_id))
                    skipped += 1
                    continue
            else:
                skipped += 1
                continue

            # Update invoice extra_data with dunning history
            invoice = await self.db.get(Invoice, candidate.invoice_id)
            if invoice:
                extra = invoice.extra_data or {}
                extra["dunning_reminder_count"] = new_count
                extra["dunning_last_sent_at"] = now.isoformat()
                history = extra.get("dunning_history", [])
                history.append({"round": new_count, "sent_at": now.isoformat()})
                extra["dunning_history"] = history
                invoice.extra_data = extra
                flag_modified(invoice, "extra_data")

                # Mark as overdue if not already
                if invoice.status == InvoiceStatus.open:
                    invoice.status = InvoiceStatus.overdue

                # After 3rd reminder: mark subscription as past_due
                if new_count >= 3:
                    sub_query = select(PlatformSubscription).where(
                        PlatformSubscription.tenant_id == candidate.tenant_id,
                        PlatformSubscription.status == SubscriptionStatus.active,
                    )
                    sub_result = await self.db.execute(sub_query)
                    sub = sub_result.scalar_one_or_none()
                    if sub:
                        sub.status = SubscriptionStatus.past_due
                        logger.info(
                            "dunning.subscription_past_due",
                            tenant_id=str(candidate.tenant_id),
                        )

            sent += 1

        await self.db.commit()
        logger.info("dunning.completed", sent=sent, skipped=skipped)
        return sent, skipped


def _render_dunning_email(
    tenant_name: str,
    invoice_number: str,
    amount_cents: int,
    days_overdue: int,
    reminder_round: int,
) -> str:
    amount_str = f"€{amount_cents / 100:,.2f}"
    ordinal = {1: "eerste", 2: "tweede", 3: "derde"}.get(reminder_round, f"{reminder_round}e")

    return f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Betalingsherinnering</h2>
        <p>Beste {tenant_name},</p>
        <p>Dit is de <strong>{ordinal} herinnering</strong> voor een openstaande factuur.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Factuurnummer</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{invoice_number}</td></tr>
            <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Openstaand bedrag</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{amount_str}</td></tr>
            <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Dagen te laat</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{days_overdue} dagen</td></tr>
        </table>
        <p>Wij verzoeken u vriendelijk het openstaande bedrag zo spoedig mogelijk te voldoen.</p>
        <p>Met vriendelijke groet,<br>{settings.platform_name}</p>
    </div>
    """
