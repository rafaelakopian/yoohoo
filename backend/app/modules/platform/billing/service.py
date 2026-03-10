"""Platform billing service: provider config, plans, subscriptions, invoices, payments."""

import enum
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.platform.billing.encryption import decrypt_api_key, encrypt_api_key
from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.billing.providers import PaymentProviderFactory
from app.modules.platform.auth.models import User
from app.modules.platform.tenant_mgmt.models import Tenant

logger = structlog.get_logger()


class ResumeMode(str, enum.Enum):
    """How to handle missed billing periods when resuming a paused subscription."""
    backfill = "backfill"      # Generate invoices for all missed months
    prorata = "prorata"        # Pro-rata invoice for current month
    next_month = "next_month"  # No invoices now, cron picks up next month


class BillingService:
    """Service for platform-level billing operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Payment Provider Configuration ───

    async def get_providers(self, tenant_id: uuid.UUID) -> list[dict]:
        """Get all payment provider configs for a tenant."""
        result = await self.db.execute(
            select(PaymentProvider).where(PaymentProvider.tenant_id == tenant_id)
        )
        providers = result.scalars().all()
        return [self._provider_to_dict(p) for p in providers]

    async def configure_provider(
        self, tenant_id: uuid.UUID, data: dict
    ) -> dict:
        """Configure a payment provider for a tenant."""
        provider_type = data["provider_type"]

        # Check for existing provider of same type
        existing = await self.db.execute(
            select(PaymentProvider).where(
                PaymentProvider.tenant_id == tenant_id,
                PaymentProvider.provider_type == provider_type,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"Provider {provider_type} is al geconfigureerd voor deze organisatie"
            )

        # If setting as default, unset other defaults
        if data.get("is_default"):
            await self._unset_default_provider(tenant_id)

        provider = PaymentProvider(
            tenant_id=tenant_id,
            provider_type=provider_type,
            is_active=True,
            is_default=data.get("is_default", False),
            api_key_encrypted=encrypt_api_key(data["api_key"]),
            api_secret_encrypted=(
                encrypt_api_key(data["api_secret"]) if data.get("api_secret") else None
            ),
            webhook_secret_encrypted=(
                encrypt_api_key(data["webhook_secret"])
                if data.get("webhook_secret")
                else None
            ),
            supported_methods=data.get("supported_methods"),
            extra_config=data.get("extra_config"),
        )
        self.db.add(provider)
        await self.db.flush()

        logger.info(
            "billing.provider_configured",
            tenant_id=str(tenant_id),
            provider_type=provider_type,
        )
        return self._provider_to_dict(provider)

    async def update_provider(
        self, tenant_id: uuid.UUID, provider_id: uuid.UUID, data: dict
    ) -> dict:
        """Update a payment provider configuration."""
        provider = await self._get_provider(tenant_id, provider_id)

        if data.get("api_key"):
            provider.api_key_encrypted = encrypt_api_key(data["api_key"])
            logger.info(
                "billing.provider_key_rotated",
                tenant_id=str(tenant_id),
                provider_type=provider.provider_type.value if hasattr(provider.provider_type, "value") else provider.provider_type,
            )
        if "api_secret" in data and data["api_secret"] is not None:
            provider.api_secret_encrypted = encrypt_api_key(data["api_secret"])
        if "webhook_secret" in data and data["webhook_secret"] is not None:
            provider.webhook_secret_encrypted = encrypt_api_key(data["webhook_secret"])
        if data.get("is_default") is not None:
            if data["is_default"]:
                await self._unset_default_provider(tenant_id)
            provider.is_default = data["is_default"]
        if data.get("is_active") is not None:
            provider.is_active = data["is_active"]
        if "supported_methods" in data:
            provider.supported_methods = data["supported_methods"]
        if "extra_config" in data:
            provider.extra_config = data["extra_config"]

        await self.db.flush()
        return self._provider_to_dict(provider)

    async def get_provider_instance(self, tenant_id: uuid.UUID, provider_type: str | None = None):
        """Get a configured payment provider instance for API calls."""
        if provider_type:
            result = await self.db.execute(
                select(PaymentProvider).where(
                    PaymentProvider.tenant_id == tenant_id,
                    PaymentProvider.provider_type == provider_type,
                    PaymentProvider.is_active == True,  # noqa: E712
                )
            )
        else:
            result = await self.db.execute(
                select(PaymentProvider).where(
                    PaymentProvider.tenant_id == tenant_id,
                    PaymentProvider.is_default == True,  # noqa: E712
                    PaymentProvider.is_active == True,  # noqa: E712
                )
            )
        config = result.scalar_one_or_none()
        if not config:
            raise NotFoundError("PaymentProvider", "default")

        api_key = decrypt_api_key(config.api_key_encrypted)
        api_secret = (
            decrypt_api_key(config.api_secret_encrypted)
            if config.api_secret_encrypted
            else None
        )
        webhook_secret = (
            decrypt_api_key(config.webhook_secret_encrypted)
            if config.webhook_secret_encrypted
            else None
        )

        return PaymentProviderFactory.create(
            config.provider_type.value,
            api_key=api_key,
            api_secret=api_secret,
            webhook_secret=webhook_secret,
        )

    # ─── Platform Plans ───

    async def list_plans(self, active_only: bool = True) -> list[dict]:
        """List platform plans."""
        query = select(PlatformPlan).order_by(PlatformPlan.sort_order)
        if active_only:
            query = query.where(PlatformPlan.is_active == True)  # noqa: E712
        result = await self.db.execute(query)
        return [self._plan_to_dict(p) for p in result.scalars().all()]

    async def create_plan(self, data: dict) -> dict:
        """Create a new platform plan."""
        plan = PlatformPlan(**data)
        self.db.add(plan)
        await self.db.flush()
        return self._plan_to_dict(plan)

    async def update_plan(self, plan_id: uuid.UUID, data: dict) -> dict:
        """Update an existing platform plan."""
        result = await self.db.execute(
            select(PlatformPlan).where(PlatformPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundError("PlatformPlan", plan_id)

        for key, value in data.items():
            if value is not None:
                setattr(plan, key, value)
        await self.db.flush()
        await self.db.refresh(plan)
        return self._plan_to_dict(plan)

    # ─── Subscriptions ───

    async def get_subscription(self, tenant_id: uuid.UUID) -> dict | None:
        """Get the active subscription for a tenant."""
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(PlatformSubscription.tenant_id == tenant_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            return None
        return self._subscription_to_dict(sub)

    async def create_subscription(
        self, tenant_id: uuid.UUID, data: dict
    ) -> dict:
        """Create a subscription for a tenant."""
        existing = await self.db.execute(
            select(PlatformSubscription).where(
                PlatformSubscription.tenant_id == tenant_id
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Tenant heeft al een actief abonnement")

        sub = PlatformSubscription(
            tenant_id=tenant_id,
            plan_id=data["plan_id"],
            status=data.get("status", "trialing"),
        )
        self.db.add(sub)
        await self.db.flush()

        # Reload with plan
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(PlatformSubscription.id == sub.id)
        )
        sub = result.scalar_one()
        return self._subscription_to_dict(sub)

    async def update_subscription(
        self, tenant_id: uuid.UUID, data: dict
    ) -> dict:
        """Update a tenant's subscription."""
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(PlatformSubscription.tenant_id == tenant_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError("PlatformSubscription", tenant_id)

        if data.get("plan_id"):
            sub.plan_id = data["plan_id"]
        if data.get("status"):
            sub.status = data["status"]
        await self.db.flush()

        # Reload with plan
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(PlatformSubscription.id == sub.id)
        )
        sub = result.scalar_one()
        logger.info("billing.subscription_changed", tenant_id=str(tenant_id))
        return self._subscription_to_dict(sub)

    async def cancel_subscription(self, tenant_id: uuid.UUID) -> dict:
        """Cancel a tenant's subscription."""
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(PlatformSubscription.tenant_id == tenant_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError("PlatformSubscription", tenant_id)

        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(sub)
        logger.info("billing.subscription_changed", tenant_id=str(tenant_id), status="cancelled")
        return self._subscription_to_dict(sub)

    # ─── Subscription Overview ───

    async def list_subscriptions_overview(
        self,
        status: str | None = None,
        plan_id: uuid.UUID | None = None,
        sort_by: str = "tenant",
        sort_dir: str = "asc",
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """List all subscriptions with enriched overview data."""
        import math
        from datetime import date

        # Base query: subscriptions with plan + tenant
        query = (
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .join(Tenant, PlatformSubscription.tenant_id == Tenant.id)
        )
        count_query = (
            select(func.count(PlatformSubscription.id))
            .join(Tenant, PlatformSubscription.tenant_id == Tenant.id)
        )

        # Filters
        if status and status != "all":
            query = query.where(PlatformSubscription.status == status)
            count_query = count_query.where(PlatformSubscription.status == status)
        if plan_id:
            query = query.where(PlatformSubscription.plan_id == plan_id)
            count_query = count_query.where(PlatformSubscription.plan_id == plan_id)

        # Sorting
        sort_map = {
            "tenant": Tenant.name,
            "plan": None,  # sort after fetch
            "start": PlatformSubscription.created_at,
            "next_invoice": None,  # sort after fetch
        }
        sort_col = sort_map.get(sort_by)
        if sort_col is not None:
            query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
        else:
            query = query.order_by(Tenant.name.asc())

        # Count + paginate
        total = (await self.db.execute(count_query)).scalar() or 0
        pages = math.ceil(total / page_size) if page_size > 0 else 1
        offset = (page - 1) * page_size
        result = await self.db.execute(query.offset(offset).limit(page_size))
        subs = result.scalars().all()

        # Collect tenant IDs for batch queries
        tenant_ids = [s.tenant_id for s in subs]

        # Batch: tenant names
        tenant_names: dict[uuid.UUID, str] = {}
        if tenant_ids:
            t_result = await self.db.execute(
                select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
            )
            tenant_names = {r.id: r.name for r in t_result.all()}

        # Batch: invoice stats per tenant (platform invoices only, paid)
        invoice_stats: dict[uuid.UUID, dict] = {}
        if tenant_ids:
            inv_result = await self.db.execute(
                select(
                    Invoice.tenant_id,
                    func.count(Invoice.id).label("count"),
                    func.coalesce(func.sum(Invoice.total_cents), 0).label("total"),
                    func.max(Invoice.created_at).label("last_date"),
                )
                .where(
                    Invoice.tenant_id.in_(tenant_ids),
                    Invoice.invoice_type == InvoiceType.platform,
                    Invoice.status == InvoiceStatus.paid,
                )
                .group_by(Invoice.tenant_id)
            )
            for row in inv_result.all():
                invoice_stats[row.tenant_id] = {
                    "count": row.count,
                    "total": int(row.total),
                    "last_date": str(row.last_date.date()) if row.last_date else None,
                }

        # Calculate next invoice date: 1st of next month
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_invoice = date(now.year + 1, 1, 1)
        else:
            next_invoice = date(now.year, now.month + 1, 1)

        # Build items
        items = []
        for sub in subs:
            plan = sub.plan
            stats = invoice_stats.get(sub.tenant_id, {})

            # next_invoice_date only for active/trialing/past_due
            nid = None
            if sub.status in (
                SubscriptionStatus.active,
                SubscriptionStatus.trialing,
                SubscriptionStatus.past_due,
            ):
                nid = str(next_invoice)

            items.append({
                "subscription_id": sub.id,
                "tenant_id": sub.tenant_id,
                "tenant_name": tenant_names.get(sub.tenant_id, ""),
                "plan_id": sub.plan_id,
                "plan_name": plan.name if plan else "",
                "plan_price_cents": plan.price_cents if plan else 0,
                "status": sub.status.value if hasattr(sub.status, "value") else sub.status,
                "started_at": sub.created_at,
                "cancelled_at": sub.cancelled_at,
                "next_invoice_date": nid,
                "last_invoice_date": stats.get("last_date"),
                "total_invoiced_cents": stats.get("total", 0),
                "invoice_count": stats.get("count", 0),
            })

        # Post-fetch sorting for plan/next_invoice
        if sort_by == "plan":
            items.sort(key=lambda x: x["plan_name"].lower(), reverse=(sort_dir == "desc"))
        elif sort_by == "next_invoice":
            items.sort(key=lambda x: x["next_invoice_date"] or "", reverse=(sort_dir == "desc"))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    async def pause_subscription(self, tenant_id: uuid.UUID) -> dict:
        """Pause a tenant's subscription."""
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(PlatformSubscription.tenant_id == tenant_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError("PlatformSubscription", tenant_id)

        if sub.status not in (SubscriptionStatus.active, SubscriptionStatus.trialing):
            raise ConflictError(
                f"Kan abonnement met status '{sub.status.value}' niet pauzeren"
            )

        sub.status = SubscriptionStatus.paused
        extra = sub.extra_data or {}
        extra["paused_at"] = datetime.now(timezone.utc).isoformat()
        sub.extra_data = extra
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(sub, "extra_data")
        await self.db.flush()
        await self.db.refresh(sub)
        logger.info("billing.subscription_paused", tenant_id=str(tenant_id))
        return self._subscription_to_dict(sub)

    async def resume_subscription(
        self,
        tenant_id: uuid.UUID,
        resume_mode: ResumeMode,
        actor_id: uuid.UUID | None = None,
        arq_pool=None,
    ) -> dict:
        """Resume a paused subscription with optional invoice generation.

        resume_mode:
          - backfill: generate invoices for every missed month since paused_at
          - prorata: generate a single pro-rata invoice for the remaining days
          - next_month: no invoices now, normal cron picks up next billing cycle
        """
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(PlatformSubscription.tenant_id == tenant_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError("PlatformSubscription", tenant_id)

        if sub.status != SubscriptionStatus.paused:
            raise ConflictError(
                f"Kan alleen een gepauzeerd abonnement hervatten (huidige status: '{sub.status.value}')"
            )

        now = datetime.now(timezone.utc)
        extra = sub.extra_data or {}
        paused_at_str = extra.get("paused_at")
        paused_at = datetime.fromisoformat(paused_at_str) if paused_at_str else sub.updated_at

        plan = sub.plan
        if not plan:
            raise NotFoundError("PlatformPlan", sub.plan_id)

        invoices_generated = 0

        if resume_mode == ResumeMode.backfill:
            invoices_generated = await self._generate_backfill_invoices(
                sub, plan, paused_at, now, arq_pool
            )
        elif resume_mode == ResumeMode.prorata:
            invoices_generated = await self._generate_prorata_invoice(
                sub, plan, now, arq_pool
            )
        # next_month: no invoices generated

        # Reactivate subscription
        sub.status = SubscriptionStatus.active
        extra["resumed_at"] = now.isoformat()
        extra["resume_mode"] = resume_mode.value
        if actor_id:
            extra["resumed_by"] = str(actor_id)
        sub.extra_data = extra
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(sub, "extra_data")
        await self.db.flush()
        await self.db.refresh(sub)

        # Invalidate subscription guard cache
        from app.modules.platform.billing.subscription_guard import invalidate_sub_status_cache
        invalidate_sub_status_cache(tenant_id)

        logger.info(
            "billing.subscription_resumed",
            tenant_id=str(tenant_id),
            resume_mode=resume_mode.value,
            invoices_generated=invoices_generated,
        )
        result_dict = self._subscription_to_dict(sub)
        result_dict["invoices_generated"] = invoices_generated
        return result_dict

    async def _generate_backfill_invoices(
        self,
        sub: PlatformSubscription,
        plan: PlatformPlan,
        paused_at: datetime,
        now: datetime,
        arq_pool=None,
    ) -> int:
        """Generate invoices for every missed month between paused_at and now."""
        from datetime import date

        # Determine the range of missed months
        start_year, start_month = paused_at.year, paused_at.month
        end_year, end_month = now.year, now.month

        generated = 0
        y, m = start_year, start_month

        while (y, m) <= (end_year, end_month):
            # Use existing generate logic per period (idempotent)
            result = await self._generate_single_period_invoice(
                sub, plan, y, m, arq_pool
            )
            if result:
                generated += 1

            # Next month
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1

        return generated

    async def _generate_prorata_invoice(
        self,
        sub: PlatformSubscription,
        plan: PlatformPlan,
        now: datetime,
        arq_pool=None,
    ) -> int:
        """Generate a pro-rata invoice for the remaining days of the current month."""
        import calendar

        days_in_month = calendar.monthrange(now.year, now.month)[1]
        remaining_days = days_in_month - now.day + 1  # Include today

        if remaining_days <= 0:
            return 0

        # Monthly price (incl BTW)
        price_cents = plan.price_cents
        if plan.interval.value == "yearly":
            price_cents = price_cents // 12

        # Pro-rata: (remaining_days / days_in_month) * price
        prorata_total = round(price_cents * remaining_days / days_in_month)
        if prorata_total <= 0:
            return 0

        tax_rate = settings.billing_tax_rate_percent / 100
        subtotal_cents = round(prorata_total / (1 + tax_rate))
        tax_cents = prorata_total - subtotal_cents

        tenant = await self.db.get(Tenant, sub.tenant_id)
        if not tenant:
            return 0

        recipient_name = tenant.name
        recipient_email = ""
        if tenant.owner_id:
            owner = await self.db.get(User, tenant.owner_id)
            if owner:
                recipient_name = owner.full_name
                recipient_email = owner.email

        due_date = now + timedelta(days=settings.billing_invoice_due_days)
        description = (
            f"Abonnement {plan.name} — pro-rata {remaining_days}/{days_in_month} dagen "
            f"{now.month:02d}/{now.year}"
        )

        invoice = await self._create_platform_invoice_with_retry(
            tenant=tenant,
            subscription=sub,
            subtotal_cents=subtotal_cents,
            tax_cents=tax_cents,
            total_cents=prorata_total,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            description=description,
            due_date=due_date,
            period_year=now.year,
            period_month=now.month,
        )

        if invoice and arq_pool and recipient_email:
            try:
                await arq_pool.enqueue_job(
                    "send_email_job",
                    to=recipient_email,
                    subject=f"Factuur {invoice.invoice_number} — {settings.platform_name}",
                    html_body=self._render_invoice_email(
                        recipient_name=recipient_name,
                        invoice_number=invoice.invoice_number,
                        description=description,
                        subtotal_cents=subtotal_cents,
                        tax_cents=tax_cents,
                        total_cents=prorata_total,
                        due_date=due_date,
                    ),
                )
            except Exception:
                logger.warning(
                    "billing.invoice_email_enqueue_failed",
                    invoice_id=str(invoice.id),
                )

        return 1 if invoice else 0

    async def _generate_single_period_invoice(
        self,
        sub: PlatformSubscription,
        plan: PlatformPlan,
        period_year: int,
        period_month: int,
        arq_pool=None,
    ) -> "Invoice | None":
        """Generate a single platform invoice for a specific period (idempotent)."""
        now = datetime.now(timezone.utc)

        # Idempotency: check if invoice already exists for this period
        existing = await self.db.execute(
            select(Invoice.id).where(
                Invoice.invoice_type == InvoiceType.platform,
                Invoice.tenant_id == sub.tenant_id,
                Invoice.extra_data["billing_period_year"].as_string()
                == str(period_year),
                Invoice.extra_data["billing_period_month"].as_string()
                == str(period_month),
            )
        )
        if existing.scalar_one_or_none():
            return None

        tenant = await self.db.get(Tenant, sub.tenant_id)
        if not tenant:
            return None

        recipient_name = tenant.name
        recipient_email = ""
        if tenant.owner_id:
            owner = await self.db.get(User, tenant.owner_id)
            if owner:
                recipient_name = owner.full_name
                recipient_email = owner.email

        # Monthly price (incl BTW)
        price_cents = plan.price_cents
        if plan.interval.value == "yearly":
            price_cents = price_cents // 12

        total_cents = price_cents
        tax_rate = settings.billing_tax_rate_percent / 100
        subtotal_cents = round(total_cents / (1 + tax_rate))
        tax_cents = total_cents - subtotal_cents

        due_date = now + timedelta(days=settings.billing_invoice_due_days)
        description = (
            f"Abonnement {plan.name} — {period_month:02d}/{period_year}"
        )

        invoice = await self._create_platform_invoice_with_retry(
            tenant=tenant,
            subscription=sub,
            subtotal_cents=subtotal_cents,
            tax_cents=tax_cents,
            total_cents=total_cents,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            description=description,
            due_date=due_date,
            period_year=period_year,
            period_month=period_month,
        )

        if invoice and arq_pool and recipient_email:
            try:
                await arq_pool.enqueue_job(
                    "send_email_job",
                    to=recipient_email,
                    subject=f"Factuur {invoice.invoice_number} — {settings.platform_name}",
                    html_body=self._render_invoice_email(
                        recipient_name=recipient_name,
                        invoice_number=invoice.invoice_number,
                        description=description,
                        subtotal_cents=subtotal_cents,
                        tax_cents=tax_cents,
                        total_cents=total_cents,
                        due_date=due_date,
                    ),
                )
            except Exception:
                logger.warning(
                    "billing.invoice_email_enqueue_failed",
                    invoice_id=str(invoice.id),
                )

        return invoice

    # ─── Invoices ───

    async def list_invoices(
        self,
        tenant_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
        invoice_type: str | None = None,
    ) -> tuple[list[dict], int]:
        """List invoices with optional filters."""
        query = select(Invoice)
        count_query = select(func.count(Invoice.id))
        filters = []

        if tenant_id:
            filters.append(Invoice.tenant_id == tenant_id)
        if status:
            filters.append(Invoice.status == status)
        if invoice_type:
            filters.append(Invoice.invoice_type == invoice_type)

        for f in filters:
            query = query.where(f)
            count_query = count_query.where(f)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
        )
        raw_invoices = result.scalars().all()

        # Look up tenant names for platform context
        tenant_ids = {i.tenant_id for i in raw_invoices if i.tenant_id}
        tenant_names: dict[uuid.UUID, str] = {}
        if tenant_ids:
            t_result = await self.db.execute(
                select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
            )
            tenant_names = {row.id: row.name for row in t_result.all()}

        invoices = []
        for inv in raw_invoices:
            d = self._invoice_to_dict(inv)
            d["tenant_name"] = tenant_names.get(inv.tenant_id)
            invoices.append(d)

        return invoices, total

    async def get_invoice(self, invoice_id: uuid.UUID) -> dict:
        """Get a single invoice by ID."""
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice", invoice_id)
        return self._invoice_to_dict(invoice)

    async def mark_invoice_paid(self, invoice_id: uuid.UUID) -> dict:
        """Manually mark an invoice as paid."""
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice", invoice_id)

        if invoice.status == InvoiceStatus.paid:
            raise ConflictError("Factuur is al betaald")

        if invoice.status not in (InvoiceStatus.open, InvoiceStatus.overdue):
            raise ConflictError(
                f"Kan factuur met status '{invoice.status.value}' niet als betaald markeren"
            )

        now = datetime.now(timezone.utc)
        invoice.status = InvoiceStatus.paid
        invoice.paid_at = now
        await self.db.commit()
        await self.db.refresh(invoice)
        return self._invoice_to_dict(invoice)

    async def create_invoice_payment(
        self,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        tenant_slug: str = "",
    ) -> dict:
        """Create a payment link (checkout URL) for an open/overdue invoice.

        Returns {"payment_id": ..., "checkout_url": ..., "invoice_number": ...}.
        """
        # 1. Fetch invoice
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id,
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice", invoice_id)

        if invoice.status not in (InvoiceStatus.open, InvoiceStatus.overdue):
            raise ConflictError(
                f"Kan geen betaallink aanmaken voor factuur met status '{invoice.status.value}'"
            )

        # 2. Get provider instance
        try:
            provider = await self.get_provider_instance(tenant_id)
        except NotFoundError:
            raise ConflictError("Geen betaalprovider geconfigureerd voor deze organisatie")

        # 3. Build checkout request
        from app.modules.platform.billing.providers.base import CreatePaymentRequest

        redirect_path = f"/org/{tenant_slug}/upgrade?payment=success" if tenant_slug else "/upgrade?payment=success"
        redirect_url = f"{settings.frontend_url}{redirect_path}"
        webhook_url = f"{settings.billing_webhook_base_url}/webhooks/mollie"

        checkout_request = CreatePaymentRequest(
            amount_cents=invoice.total_cents,
            currency=invoice.currency,
            description=invoice.description or invoice.invoice_number,
            redirect_url=redirect_url,
            webhook_url=webhook_url,
            metadata={
                "invoice_id": str(invoice.id),
                "tenant_id": str(tenant_id),
            },
        )

        # 4. Create checkout session
        payment_result = await provider.create_checkout_session(checkout_request)

        # 5. Create Payment record
        payment = Payment(
            invoice_id=invoice.id,
            tenant_id=tenant_id,
            provider_type=self._detect_provider_type(provider),
            provider_payment_id=payment_result.provider_payment_id,
            amount_cents=invoice.total_cents,
            currency=invoice.currency,
            status=PaymentStatus.pending,
            idempotency_key=f"inv_{invoice.id}_{uuid.uuid4().hex[:8]}",
        )
        self.db.add(payment)
        await self.db.flush()

        logger.info(
            "billing.payment_created",
            invoice_id=str(invoice.id),
            payment_id=str(payment.id),
            tenant_id=str(tenant_id),
        )

        return {
            "payment_id": payment.id,
            "checkout_url": payment_result.checkout_url,
            "invoice_number": invoice.invoice_number,
        }

    @staticmethod
    def _detect_provider_type(provider) -> str:
        """Detect provider type from instance class name."""
        from app.modules.platform.billing.providers.mollie import MollieProvider
        from app.modules.platform.billing.providers.stripe_provider import StripeProvider

        if isinstance(provider, MollieProvider):
            return "mollie"
        if isinstance(provider, StripeProvider):
            return "stripe"
        return "mollie"

    async def list_platform_invoices_for_tenant(
        self,
        tenant_id: uuid.UUID,
        statuses: list[str] | None = None,
    ) -> list[dict]:
        """List platform invoices for a specific tenant."""
        query = (
            select(Invoice)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.invoice_type == InvoiceType.platform,
            )
            .order_by(Invoice.created_at.desc())
        )

        if statuses:
            query = query.where(Invoice.status.in_(statuses))

        result = await self.db.execute(query)
        invoices = result.scalars().all()
        return [self._invoice_to_dict(inv) for inv in invoices]

    # ─── Platform Invoice Generation ───

    async def generate_platform_invoices(
        self,
        period_year: int,
        period_month: int,
        arq_pool=None,
    ) -> dict:
        """Generate platform invoices for all active subscriptions.

        Idempotent: skips subscriptions that already have an invoice for the
        given billing period (checked via extra_data JSONB).
        """
        now = datetime.now(timezone.utc)

        # Fetch active subscriptions with their plans
        result = await self.db.execute(
            select(PlatformSubscription)
            .options(selectinload(PlatformSubscription.plan))
            .where(
                PlatformSubscription.status.in_([
                    SubscriptionStatus.active,
                    SubscriptionStatus.past_due,
                ])
            )
        )
        subscriptions = result.scalars().all()

        generated = 0
        skipped = 0

        for sub in subscriptions:
            # Idempotency check: does an invoice already exist for this period?
            existing = await self.db.execute(
                select(Invoice.id).where(
                    Invoice.invoice_type == InvoiceType.platform,
                    Invoice.tenant_id == sub.tenant_id,
                    Invoice.extra_data["billing_period_year"].as_string()
                    == str(period_year),
                    Invoice.extra_data["billing_period_month"].as_string()
                    == str(period_month),
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            # Lookup tenant + owner for recipient info
            tenant = await self.db.get(Tenant, sub.tenant_id)
            if not tenant:
                skipped += 1
                continue

            recipient_name = tenant.name
            recipient_email = ""
            if tenant.owner_id:
                owner = await self.db.get(User, tenant.owner_id)
                if owner:
                    recipient_name = owner.full_name
                    recipient_email = owner.email

            # Calculate amounts
            plan = sub.plan
            if not plan:
                skipped += 1
                continue

            # Normalize to monthly price (price_cents is incl BTW)
            price_cents = plan.price_cents
            if plan.interval.value == "yearly":
                price_cents = price_cents // 12

            # Back-calculate excl BTW from incl BTW price
            total_cents = price_cents
            tax_rate = settings.billing_tax_rate_percent / 100
            subtotal_cents = round(total_cents / (1 + tax_rate))
            tax_cents = total_cents - subtotal_cents

            due_date = now + timedelta(days=settings.billing_invoice_due_days)
            description = (
                f"Abonnement {plan.name} — {period_month:02d}/{period_year}"
            )

            # Create invoice with retry on invoice_number collision
            invoice = await self._create_platform_invoice_with_retry(
                tenant=tenant,
                subscription=sub,
                subtotal_cents=subtotal_cents,
                tax_cents=tax_cents,
                total_cents=total_cents,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                description=description,
                due_date=due_date,
                period_year=period_year,
                period_month=period_month,
            )
            if not invoice:
                skipped += 1
                continue

            generated += 1

            # Enqueue invoice email
            if arq_pool and recipient_email:
                try:
                    await arq_pool.enqueue_job(
                        "send_email_job",
                        to=recipient_email,
                        subject=f"Factuur {invoice.invoice_number} — {settings.platform_name}",
                        html_body=self._render_invoice_email(
                            recipient_name=recipient_name,
                            invoice_number=invoice.invoice_number,
                            description=description,
                            subtotal_cents=subtotal_cents,
                            tax_cents=tax_cents,
                            total_cents=total_cents,
                            due_date=due_date,
                        ),
                    )
                except Exception:
                    logger.warning(
                        "billing.invoice_email_enqueue_failed",
                        invoice_id=str(invoice.id),
                    )

        logger.info(
            "billing.platform_invoices_generated",
            generated=generated,
            skipped=skipped,
            period=f"{period_year}-{period_month:02d}",
        )
        return {"generated": generated, "skipped": skipped}

    async def _next_platform_invoice_number(self, year: int) -> str:
        """Get next sequential platform invoice number."""
        prefix = f"{settings.billing_invoice_prefix}-PLT-{year}-"
        max_result = await self.db.execute(
            select(func.max(Invoice.invoice_number)).where(
                Invoice.invoice_number.like(f"{prefix}%")
            )
        )
        last_number = max_result.scalar()
        if last_number:
            last_seq = int(last_number.rsplit("-", 1)[1])
            seq = last_seq + 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    async def _create_platform_invoice_with_retry(
        self,
        tenant: "Tenant",
        subscription: PlatformSubscription,
        subtotal_cents: int,
        tax_cents: int,
        total_cents: int,
        recipient_name: str,
        recipient_email: str,
        description: str,
        due_date: datetime,
        period_year: int,
        period_month: int,
        max_retries: int = 3,
    ) -> Invoice | None:
        """Create platform invoice with retry on invoice_number collision."""
        for attempt in range(max_retries):
            invoice_number = await self._next_platform_invoice_number(
                period_year
            )
            invoice = Invoice(
                invoice_number=invoice_number,
                invoice_type=InvoiceType.platform,
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                subtotal_cents=subtotal_cents,
                tax_cents=tax_cents,
                total_cents=total_cents,
                currency=settings.billing_default_currency,
                status=InvoiceStatus.open,
                description=description,
                line_items=[
                    {
                        "description": description,
                        "subtotal_cents": subtotal_cents,
                        "tax_cents": tax_cents,
                    }
                ],
                due_date=due_date,
                extra_data={
                    "billing_period_year": period_year,
                    "billing_period_month": period_month,
                },
            )
            self.db.add(invoice)
            try:
                await self.db.flush()
                return invoice
            except IntegrityError as e:
                await self.db.rollback()
                constraint = str(e.orig) if e.orig else str(e)
                if "invoice_number" not in constraint and attempt == max_retries - 1:
                    logger.error(
                        "billing.platform_invoice_create_failed",
                        error=str(e),
                        tenant_id=str(tenant.id),
                    )
                    return None
                logger.warning(
                    "billing.platform_invoice_number_collision",
                    invoice_number=invoice_number,
                    attempt=attempt + 1,
                )
        return None

    @staticmethod
    def _render_invoice_email(
        recipient_name: str,
        invoice_number: str,
        description: str,
        subtotal_cents: int,
        tax_cents: int,
        total_cents: int,
        due_date: datetime,
    ) -> str:
        """Render platform invoice email HTML."""
        def fmt(cents: int) -> str:
            return f"€{cents / 100:,.2f}"

        due_str = due_date.strftime("%d-%m-%Y")
        return f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Factuur {invoice_number}</h2>
            <p>Beste {recipient_name},</p>
            <p>Hierbij ontvangt u uw factuur voor {description}.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Factuurnummer</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{invoice_number}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Omschrijving</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{description}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Subtotaal</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{fmt(subtotal_cents)}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>BTW ({settings.billing_tax_rate_percent}%)</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{fmt(tax_cents)}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Totaal</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>{fmt(total_cents)}</strong></td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Vervaldatum</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{due_str}</td></tr>
            </table>
            <p>Wij verzoeken u vriendelijk het bedrag vóór de vervaldatum te voldoen.</p>
            <p>Met vriendelijke groet,<br>{settings.platform_name}</p>
        </div>
        """

    # ─── Payments ───

    async def list_payments(
        self,
        tenant_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """List payments with optional filters."""
        query = select(Payment)
        count_query = select(func.count(Payment.id))
        filters = []

        if tenant_id:
            filters.append(Payment.tenant_id == tenant_id)
        if invoice_id:
            filters.append(Payment.invoice_id == invoice_id)

        for f in filters:
            query = query.where(f)
            count_query = count_query.where(f)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(Payment.created_at.desc()).offset(skip).limit(limit)
        )
        payments = [self._payment_to_dict(p) for p in result.scalars().all()]
        return payments, total

    async def create_refund(
        self, payment_id: uuid.UUID, amount_cents: int | None = None, description: str | None = None
    ) -> dict:
        """Create a refund for a payment."""
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise NotFoundError("Payment", payment_id)

        if payment.status != PaymentStatus.paid:
            raise ConflictError("Alleen betaalde betalingen kunnen worden terugbetaald")

        refund_amount = amount_cents or payment.amount_cents

        # Get provider instance
        provider = await self.get_provider_instance(
            payment.tenant_id, payment.provider_type.value
        )
        await provider.create_refund(
            payment.provider_payment_id, refund_amount, description
        )

        payment.refund_amount_cents += refund_amount
        if payment.refund_amount_cents >= payment.amount_cents:
            payment.status = PaymentStatus.refunded
        else:
            payment.status = PaymentStatus.partially_refunded
        await self.db.flush()

        logger.info(
            "billing.refund_created",
            payment_id=str(payment_id),
            amount_cents=refund_amount,
        )
        return self._payment_to_dict(payment)

    # ─── Helpers ───

    async def _get_provider(
        self, tenant_id: uuid.UUID, provider_id: uuid.UUID
    ) -> PaymentProvider:
        result = await self.db.execute(
            select(PaymentProvider).where(
                PaymentProvider.id == provider_id,
                PaymentProvider.tenant_id == tenant_id,
            )
        )
        provider = result.scalar_one_or_none()
        if not provider:
            raise NotFoundError("PaymentProvider", provider_id)
        return provider

    async def _unset_default_provider(self, tenant_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(PaymentProvider).where(
                PaymentProvider.tenant_id == tenant_id,
                PaymentProvider.is_default == True,  # noqa: E712
            )
        )
        for p in result.scalars().all():
            p.is_default = False
        await self.db.flush()

    @staticmethod
    def _provider_to_dict(provider: PaymentProvider) -> dict:
        return {
            "id": provider.id,
            "tenant_id": provider.tenant_id,
            "provider_type": provider.provider_type.value if hasattr(provider.provider_type, "value") else provider.provider_type,
            "is_active": provider.is_active,
            "is_default": provider.is_default,
            "provider_account_id": provider.provider_account_id,
            "supported_methods": provider.supported_methods,
            "extra_config": provider.extra_config,
            "has_api_key": bool(provider.api_key_encrypted),
            "has_api_secret": bool(provider.api_secret_encrypted),
            "has_webhook_secret": bool(provider.webhook_secret_encrypted),
            "created_at": provider.created_at,
            "updated_at": provider.updated_at,
        }

    @staticmethod
    def _plan_to_dict(plan: PlatformPlan) -> dict:
        return {
            "id": plan.id,
            "name": plan.name,
            "slug": plan.slug,
            "description": plan.description,
            "price_cents": plan.price_cents,
            "currency": plan.currency,
            "interval": plan.interval.value if hasattr(plan.interval, "value") else plan.interval,
            "max_students": plan.max_students,
            "max_teachers": plan.max_teachers,
            "features": plan.features,
            "is_active": plan.is_active,
            "sort_order": plan.sort_order,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

    @staticmethod
    def _subscription_to_dict(sub: PlatformSubscription) -> dict:
        d = {
            "id": sub.id,
            "tenant_id": sub.tenant_id,
            "plan_id": sub.plan_id,
            "status": sub.status.value if hasattr(sub.status, "value") else sub.status,
            "provider_subscription_id": sub.provider_subscription_id,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
            "trial_end": sub.trial_end,
            "cancelled_at": sub.cancelled_at,
            "created_at": sub.created_at,
            "updated_at": sub.updated_at,
        }
        if hasattr(sub, "plan") and sub.plan:
            d["plan"] = BillingService._plan_to_dict(sub.plan)
        else:
            d["plan"] = None
        return d

    @staticmethod
    def _invoice_to_dict(invoice: Invoice) -> dict:
        extra = invoice.extra_data or {}
        return {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "invoice_type": invoice.invoice_type.value if hasattr(invoice.invoice_type, "value") else invoice.invoice_type,
            "tenant_id": invoice.tenant_id,
            "subscription_id": invoice.subscription_id,
            "recipient_name": invoice.recipient_name,
            "recipient_email": invoice.recipient_email,
            "recipient_address": invoice.recipient_address,
            "subtotal_cents": invoice.subtotal_cents,
            "tax_cents": invoice.tax_cents,
            "total_cents": invoice.total_cents,
            "currency": invoice.currency,
            "status": invoice.status.value if hasattr(invoice.status, "value") else invoice.status,
            "description": invoice.description,
            "line_items": invoice.line_items,
            "due_date": invoice.due_date,
            "paid_at": invoice.paid_at,
            "dunning_count": extra.get("dunning_reminder_count", 0),
            "dunning_last_sent_at": extra.get("dunning_last_sent_at"),
            "created_at": invoice.created_at,
            "updated_at": invoice.updated_at,
        }

    @staticmethod
    def _payment_to_dict(payment: Payment) -> dict:
        return {
            "id": payment.id,
            "invoice_id": payment.invoice_id,
            "tenant_id": payment.tenant_id,
            "provider_type": payment.provider_type.value if hasattr(payment.provider_type, "value") else payment.provider_type,
            "provider_payment_id": payment.provider_payment_id,
            "amount_cents": payment.amount_cents,
            "currency": payment.currency,
            "status": payment.status.value if hasattr(payment.status, "value") else payment.status,
            "payment_method": payment.payment_method,
            "failure_reason": payment.failure_reason,
            "refund_amount_cents": payment.refund_amount_cents,
            "paid_at": payment.paid_at,
            "created_at": payment.created_at,
            "updated_at": payment.updated_at,
        }
