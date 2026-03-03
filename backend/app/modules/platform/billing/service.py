"""Platform billing service: provider config, plans, subscriptions, invoices, payments."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.platform.billing.encryption import decrypt_api_key, encrypt_api_key
from app.modules.platform.billing.models import (
    Invoice,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PlatformPlan,
    PlatformSubscription,
)
from app.modules.platform.billing.providers import PaymentProviderFactory

logger = structlog.get_logger()


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

    # ─── Invoices ───

    async def list_invoices(
        self,
        tenant_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """List invoices with optional filters."""
        query = select(Invoice)
        count_query = select(func.count(Invoice.id))
        filters = []

        if tenant_id:
            filters.append(Invoice.tenant_id == tenant_id)
        if status:
            filters.append(Invoice.status == status)

        for f in filters:
            query = query.where(f)
            count_query = count_query.where(f)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
        )
        invoices = [self._invoice_to_dict(i) for i in result.scalars().all()]
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
