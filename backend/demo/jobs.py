"""Demo job runner — manual cron job triggers and invoice date manipulation."""

import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.db.central import async_session_factory
from app.db.tenant import tenant_db_manager
from sqlalchemy.orm.attributes import flag_modified

from app.modules.platform.billing.models import (
    FeatureTrialStatus,
    Invoice,
    InvoiceStatus,
    InvoiceType,
    TenantFeatureOverride,
    TenantFeatureTrial,
)
from app.modules.platform.tenant_mgmt.models import Tenant
from app.modules.products.school.billing.models import (
    TuitionInvoice,
    TuitionInvoiceStatus,
)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


async def _get_demo_tenants():
    """Get all demo tenants from central DB."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.slug.like("demo-%"))
        )
        return list(result.scalars().all())


async def _create_arq_pool():
    """Create arq Redis pool for email job enqueuing."""
    from arq import create_pool
    from arq.connections import RedisSettings

    return await create_pool(RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.arq_redis_db,
    ))


# ---------------------------------------------------------------------------
# Job runners
# ---------------------------------------------------------------------------


async def run_dunning() -> dict:
    """Run dunning reminders for demo orgs only."""
    from app.modules.platform.finance.service import FinanceService

    tenants = await _get_demo_tenants()
    if not tenants:
        return {"processed": 0, "emails_sent": 0, "message": "Geen demo-orgs gevonden"}

    arq_pool = await _create_arq_pool()
    try:
        total_sent = 0
        total_skipped = 0

        async with async_session_factory() as db:
            service = FinanceService(db)
            for tenant in tenants:
                sent, skipped = await service.send_dunning_reminders(
                    arq_pool, tenant_id=tenant.id
                )
                total_sent += sent
                total_skipped += skipped
                if sent > 0:
                    _log(f"  {tenant.name}: {sent} verstuurd, {skipped} overgeslagen")

        return {"processed": total_sent + total_skipped, "emails_sent": total_sent}
    finally:
        await arq_pool.close()


async def run_trials() -> dict:
    """Run trial expiry + 7-day warnings."""
    from app.core.jobs.feature_trials import _send_trial_expiring_warnings
    from app.modules.platform.billing.trial_service import expire_trials

    async with async_session_factory() as db:
        warnings = await _send_trial_expiring_warnings(db)
        expired = await expire_trials(db)
        await db.commit()

    _log(f"  {expired} trials verlopen, {warnings} waarschuwingen verstuurd")
    return {"expired": expired, "warnings_sent": warnings}


async def run_purge() -> dict:
    """Run retention purge + 60%/90% warnings."""
    from app.core.jobs.feature_trials import _send_retention_warnings
    from app.modules.platform.billing.trial_service import purge_expired_retention

    async with async_session_factory() as db:
        warnings = await _send_retention_warnings(db)
        purged = await purge_expired_retention(db)
        await db.commit()

    _log(f"  {purged} trials gepurged, {warnings} waarschuwingen verstuurd")
    return {"purged": purged, "retention_warnings": warnings}


async def run_generate_platform_invoices(
    period_year: int | None = None,
    period_month: int | None = None,
) -> dict:
    """Generate platform invoices for all tenants with active subscriptions.

    Defaults to previous month if no period specified.
    """
    from app.modules.platform.billing.service import BillingService

    now = datetime.now(timezone.utc)
    if period_year is None or period_month is None:
        if now.month == 1:
            period_month, period_year = 12, now.year - 1
        else:
            period_month, period_year = now.month - 1, now.year

    arq_pool = await _create_arq_pool()
    try:
        async with async_session_factory() as db:
            service = BillingService(db)
            result = await service.generate_platform_invoices(
                period_year=period_year,
                period_month=period_month,
                arq_pool=arq_pool,
            )
            await db.commit()
        _log(f"  Platform facturen: {result['generated']} aangemaakt, {result['skipped']} overgeslagen (periode {period_month:02d}/{period_year})")
        return result
    finally:
        await arq_pool.close()


# ---------------------------------------------------------------------------
# Invoice date manipulation
# ---------------------------------------------------------------------------


async def advance_invoice_dates(days: int) -> dict:
    """Shift due_dates backward on all open demo-org invoices.

    Updates both tenant TuitionInvoice and central Invoice records
    (creating central records if needed, so dunning can find them).
    """
    tenants = await _get_demo_tenants()
    if not tenants:
        return {"updated": 0, "invoices": []}

    delta = timedelta(days=days)
    all_updates: list[dict] = []

    # Phase 1: Update TuitionInvoice due_dates in tenant DBs + collect data
    for tenant in tenants:
        slug = tenant.slug
        await tenant_db_manager.get_engine(slug)
        factory = tenant_db_manager._session_factories[slug]

        async with factory() as tenant_db:
            result = await tenant_db.execute(
                select(TuitionInvoice).where(
                    TuitionInvoice.status.in_([
                        TuitionInvoiceStatus.draft,
                        TuitionInvoiceStatus.sent,
                        TuitionInvoiceStatus.overdue,
                    ]),
                    TuitionInvoice.due_date.isnot(None),
                )
            )
            invoices = list(result.scalars().all())

            for inv in invoices:
                old_due = inv.due_date
                new_due = old_due - delta
                inv.due_date = new_due
                all_updates.append({
                    "tenant_id": tenant.id,
                    "nr": inv.invoice_number,
                    "old_due": old_due,
                    "new_due": new_due,
                    "payer_name": inv.payer_name,
                    "payer_email": inv.payer_email,
                    "subtotal_cents": inv.subtotal_cents,
                    "total_cents": inv.total_cents,
                    "currency": inv.currency,
                })

            await tenant_db.commit()

    # Phase 2: Ensure central Invoice records exist (for dunning system)
    async with async_session_factory() as db:
        for data in all_updates:
            existing = await db.execute(
                select(Invoice).where(Invoice.invoice_number == data["nr"])
            )
            central_inv = existing.scalar_one_or_none()

            if not central_inv:
                central_inv = Invoice(
                    invoice_number=data["nr"],
                    invoice_type=InvoiceType.tuition,
                    tenant_id=data["tenant_id"],
                    recipient_name=data["payer_name"],
                    recipient_email=data["payer_email"],
                    subtotal_cents=data["subtotal_cents"],
                    tax_cents=0,
                    total_cents=data["total_cents"],
                    currency=data["currency"],
                    status=InvoiceStatus.open,
                    due_date=data["new_due"],
                )
                db.add(central_inv)
            else:
                central_inv.due_date = data["new_due"]
                if central_inv.status == InvoiceStatus.draft:
                    central_inv.status = InvoiceStatus.open
                # Clear daily dunning rate-limit so next dunning run can send
                extra = central_inv.extra_data or {}
                if "dunning_last_sent_at" in extra:
                    del extra["dunning_last_sent_at"]
                    central_inv.extra_data = extra
                    flag_modified(central_inv, "extra_data")

        await db.commit()

    _log(f"  {len(all_updates)} facturen verschoven met {days} dagen")
    return {
        "updated": len(all_updates),
        "invoices": [
            {
                "nr": d["nr"],
                "old_due": str(d["old_due"].date()),
                "new_due": str(d["new_due"].date()),
            }
            for d in all_updates
        ],
    }


# ---------------------------------------------------------------------------
# Status overview
# ---------------------------------------------------------------------------


async def show_status() -> dict:
    """Show current demo state: orgs, trials, overrides, invoices + dunning status."""
    tenants = await _get_demo_tenants()
    if not tenants:
        return {"orgs": [], "message": "Geen demo-orgs gevonden"}

    now = datetime.now(timezone.utc)
    orgs = []

    async with async_session_factory() as db:
        for tenant in tenants:
            org: dict = {
                "name": tenant.name,
                "slug": tenant.slug,
                "trials": [],
                "overrides": [],
                "invoices": [],
            }

            # Feature trials
            trial_result = await db.execute(
                select(TenantFeatureTrial).where(
                    TenantFeatureTrial.tenant_id == tenant.id
                )
            )
            for trial in trial_result.scalars().all():
                entry: dict = {
                    "feature": trial.feature_name,
                    "status": trial.status.value,
                }
                if trial.trial_expires_at:
                    entry["expires_at"] = str(trial.trial_expires_at.date())
                    if trial.status == FeatureTrialStatus.trialing:
                        entry["days_left"] = (trial.trial_expires_at - now).days
                org["trials"].append(entry)

            # Feature overrides
            override_result = await db.execute(
                select(TenantFeatureOverride).where(
                    TenantFeatureOverride.tenant_id == tenant.id
                )
            )
            for ov in override_result.scalars().all():
                entry = {"feature": ov.feature_name}
                if ov.force_off:
                    entry["type"] = "force_off"
                    entry["reason"] = ov.force_off_reason
                elif ov.force_on:
                    entry["type"] = "force_on"
                org["overrides"].append(entry)

            # Central invoices (dunning data)
            central_map: dict[str, dict] = {}
            inv_result = await db.execute(
                select(Invoice).where(Invoice.tenant_id == tenant.id)
            )
            for inv in inv_result.scalars().all():
                extra = inv.extra_data or {}
                central_map[inv.invoice_number] = {
                    "central_status": inv.status.value,
                    "dunning_count": extra.get("dunning_reminder_count", 0),
                    "dunning_last": extra.get("dunning_last_sent_at"),
                }

            # Tenant DB invoices (actual data)
            slug = tenant.slug
            try:
                await tenant_db_manager.get_engine(slug)
                factory = tenant_db_manager._session_factories[slug]
                async with factory() as tenant_db:
                    tinv_result = await tenant_db.execute(select(TuitionInvoice))
                    for tinv in tinv_result.scalars().all():
                        dunning = central_map.get(tinv.invoice_number, {})
                        days_overdue = None
                        if tinv.due_date:
                            days_overdue = (now - tinv.due_date).days
                            if days_overdue < 0:
                                days_overdue = None  # not yet overdue

                        org["invoices"].append({
                            "nr": tinv.invoice_number,
                            "status": tinv.status.value,
                            "total": f"EUR {tinv.total_cents / 100:.2f}",
                            "due_date": str(tinv.due_date.date()) if tinv.due_date else None,
                            "days_overdue": days_overdue,
                            "dunning_count": dunning.get("dunning_count", 0),
                            "dunning_last": dunning.get("dunning_last"),
                        })
            except Exception:
                pass

            orgs.append(org)

    return {"orgs": orgs}
