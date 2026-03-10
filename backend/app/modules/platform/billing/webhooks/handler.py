"""Idempotent webhook event handler. Processes payment status changes."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    Payment,
    PaymentStatus,
    PlatformSubscription,
    SubscriptionStatus,
    WebhookEvent,
)

logger = structlog.get_logger()


class WebhookHandler:
    """Handles incoming webhook events idempotently."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_event(
        self,
        provider_type: str,
        event_id: str,
        event_type: str,
        payment_id: str | None = None,
        payload: dict | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> bool:
        """Process a webhook event. Returns True if processed, False if duplicate.

        Idempotency: duplicate events (same provider_type + event_id) are
        acknowledged with 200 but not reprocessed.
        """
        # Check for duplicate
        existing = await self.db.execute(
            select(WebhookEvent).where(
                WebhookEvent.provider_type == provider_type,
                WebhookEvent.provider_event_id == event_id,
            )
        )
        if existing.scalar_one_or_none():
            logger.info(
                "webhook.duplicate_skipped",
                provider=provider_type,
                event_id=event_id,
            )
            return False

        # Record the event
        event = WebhookEvent(
            provider_type=provider_type,
            provider_event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            payload=self._sanitize_payload(payload),
            processed=False,
        )
        self.db.add(event)
        await self.db.flush()

        # Process based on event type
        try:
            if event_type.startswith("payment."):
                await self._handle_payment_event(event_type, payment_id, payload)

            event.processed = True
            event.processed_at = datetime.now(timezone.utc)
            await self.db.flush()

            logger.info(
                "webhook.processed",
                provider=provider_type,
                event_id=event_id,
                event_type=event_type,
            )
            return True

        except Exception as e:
            event.processing_error = str(e)
            await self.db.flush()
            logger.error(
                "webhook.processing_error",
                provider=provider_type,
                event_id=event_id,
                error=str(e),
            )
            raise

    async def _handle_payment_event(
        self, event_type: str, payment_id: str | None, payload: dict | None
    ) -> None:
        """Handle payment-related webhook events."""
        if not payment_id:
            return

        # Find the payment by provider_payment_id
        result = await self.db.execute(
            select(Payment).where(Payment.provider_payment_id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            logger.warning("webhook.payment_not_found", provider_payment_id=payment_id)
            return

        # Map event type to status
        new_status = self._event_to_status(event_type)
        if not new_status:
            return

        old_status = payment.status
        payment.status = new_status

        if new_status == PaymentStatus.paid:
            payment.paid_at = datetime.now(timezone.utc)

        await self.db.flush()

        # Update invoice status if payment is complete
        if new_status == PaymentStatus.paid:
            await self._update_invoice_status(payment.invoice_id, InvoiceStatus.paid)
            # Auto-resume paused subscription if all platform invoices are now paid
            await self._try_auto_resume(payment.invoice_id, payment.tenant_id)

        logger.info(
            "billing.payment_status_changed",
            payment_id=str(payment.id),
            old_status=old_status.value if hasattr(old_status, "value") else old_status,
            new_status=new_status.value,
            provider_payment_id=payment_id,
        )

    async def _update_invoice_status(
        self, invoice_id: uuid.UUID, status: InvoiceStatus
    ) -> None:
        """Update invoice status when payment succeeds."""
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if invoice:
            invoice.status = status
            if status == InvoiceStatus.paid:
                invoice.paid_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def _try_auto_resume(
        self, invoice_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        """Auto-resume a paused subscription when all platform invoices are paid."""
        # Check if the paid invoice is a platform invoice
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice or invoice.invoice_type != InvoiceType.platform:
            return

        # Count remaining open/overdue platform invoices for this tenant
        open_count = await self._count_open_platform_invoices(tenant_id)
        if open_count > 0:
            return

        # Check if subscription is paused
        sub = await self._get_subscription(tenant_id)
        if not sub or sub.status != SubscriptionStatus.paused:
            return

        # Auto-resume with next_month mode (system action)
        from app.modules.platform.billing.service import BillingService, ResumeMode

        billing_service = BillingService(self.db)
        await billing_service.resume_subscription(
            tenant_id=tenant_id,
            resume_mode=ResumeMode.next_month,
            actor_id=None,  # system action
        )
        logger.info(
            "billing.auto_resumed_after_payment",
            tenant_id=str(tenant_id),
            invoice_id=str(invoice_id),
        )

    async def _count_open_platform_invoices(self, tenant_id: uuid.UUID) -> int:
        """Count open/overdue platform invoices for a tenant."""
        result = await self.db.execute(
            select(func.count(Invoice.id)).where(
                Invoice.tenant_id == tenant_id,
                Invoice.invoice_type == InvoiceType.platform,
                Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.overdue]),
            )
        )
        return result.scalar() or 0

    async def _get_subscription(
        self, tenant_id: uuid.UUID
    ) -> PlatformSubscription | None:
        """Get the subscription for a tenant."""
        result = await self.db.execute(
            select(PlatformSubscription).where(
                PlatformSubscription.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _event_to_status(event_type: str) -> PaymentStatus | None:
        """Map webhook event types to payment statuses."""
        mapping = {
            "payment.paid": PaymentStatus.paid,
            "payment.failed": PaymentStatus.failed,
            "payment.cancelled": PaymentStatus.cancelled,
            "payment.expired": PaymentStatus.expired,
            "payment.refunded": PaymentStatus.refunded,
            "payment.pending": PaymentStatus.pending,
            "payment.processing": PaymentStatus.processing,
        }
        return mapping.get(event_type)

    @staticmethod
    def _sanitize_payload(payload: dict | None) -> dict | None:
        """Remove sensitive data from webhook payloads before storage."""
        if not payload:
            return payload

        sanitized = dict(payload)
        # Remove any potential PCI data (should never be present, but defense in depth)
        sensitive_keys = {
            "card_number", "cvv", "cvc", "expiry", "pan",
            "account_number", "routing_number",
        }
        for key in sensitive_keys:
            sanitized.pop(key, None)
        return sanitized
