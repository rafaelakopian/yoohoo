"""Tests for webhook handling: idempotency, event processing."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    Payment,
    PaymentStatus,
    ProviderType,
)
from app.modules.platform.billing.webhooks.handler import WebhookHandler
from app.modules.platform.billing.webhooks.verification import (
    extract_mollie_payment_id,
)
from app.modules.platform.tenant_mgmt.models import Tenant


@pytest.mark.asyncio
class TestWebhookIdempotency:
    async def test_duplicate_event_is_skipped(self, db_session: AsyncSession):
        """Same event processed twice should skip on second attempt."""
        handler = WebhookHandler(db_session)
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        # First processing — should return True
        result1 = await handler.process_event(
            provider_type="mollie",
            event_id=event_id,
            event_type="payment.paid",
            payment_id="tr_test123",
            payload={"id": "tr_test123"},
        )
        await db_session.flush()
        assert result1 is True

        # Second processing — should return False (duplicate)
        result2 = await handler.process_event(
            provider_type="mollie",
            event_id=event_id,
            event_type="payment.paid",
            payment_id="tr_test123",
        )
        assert result2 is False

    async def test_different_events_both_processed(self, db_session: AsyncSession):
        """Different events should both be processed."""
        handler = WebhookHandler(db_session)

        result1 = await handler.process_event(
            provider_type="mollie",
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="payment.paid",
        )
        assert result1 is True

        result2 = await handler.process_event(
            provider_type="stripe",
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="payment.failed",
        )
        assert result2 is True


@pytest.mark.asyncio
class TestWebhookPaymentUpdate:
    async def test_payment_status_updated_on_webhook(self, db_session: AsyncSession):
        """Webhook should update payment status in database."""
        tenant = Tenant(name="Webhook Test", slug=f"wh-test-{uuid.uuid4().hex[:8]}")
        db_session.add(tenant)
        await db_session.flush()
        tenant_id = tenant.id

        # Create an invoice and payment
        invoice = Invoice(
            invoice_number=f"PS-WH-{uuid.uuid4().hex[:6]}",
            invoice_type=InvoiceType.platform,
            tenant_id=tenant_id,
            recipient_name="Test",
            recipient_email="test@example.com",
            subtotal_cents=5900,
            total_cents=7139,
        )
        db_session.add(invoice)
        await db_session.flush()

        payment = Payment(
            invoice_id=invoice.id,
            tenant_id=tenant_id,
            provider_type=ProviderType.mollie,
            provider_payment_id="tr_webhook_test",
            amount_cents=7139,
            status=PaymentStatus.pending,
        )
        db_session.add(payment)
        await db_session.flush()

        # Process a webhook event
        handler = WebhookHandler(db_session)
        await handler.process_event(
            provider_type="mollie",
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="payment.paid",
            payment_id="tr_webhook_test",
            payload={"id": "tr_webhook_test"},
        )
        await db_session.flush()

        # Verify payment status was updated
        result = await db_session.execute(
            select(Payment).where(Payment.id == payment.id)
        )
        updated = result.scalar_one()
        assert updated.status == PaymentStatus.paid
        assert updated.paid_at is not None

        # Verify invoice status was also updated
        result = await db_session.execute(
            select(Invoice).where(Invoice.id == invoice.id)
        )
        inv = result.scalar_one()
        assert inv.status == InvoiceStatus.paid


@pytest.mark.asyncio
class TestMollieWebhookParsing:
    async def test_extract_payment_id(self):
        """Extract payment ID from Mollie webhook body."""
        body = b"id=tr_Hm45k87KpJ"
        assert extract_mollie_payment_id(body) == "tr_Hm45k87KpJ"

    async def test_extract_payment_id_with_extra_params(self):
        """Handle additional params in webhook body."""
        body = b"id=tr_Hm45k87KpJ&extra=value"
        assert extract_mollie_payment_id(body) == "tr_Hm45k87KpJ"

    async def test_extract_payment_id_missing(self):
        """Return None when no ID in body."""
        body = b"invalid=data"
        assert extract_mollie_payment_id(body) is None

    async def test_extract_payment_id_empty(self):
        """Return None for empty body."""
        body = b""
        assert extract_mollie_payment_id(body) is None


@pytest.mark.asyncio
class TestPayloadSanitization:
    async def test_sensitive_fields_removed(self, db_session: AsyncSession):
        """Verify sensitive PCI data is stripped from stored payloads."""
        handler = WebhookHandler(db_session)
        payload = {
            "id": "tr_test",
            "status": "paid",
            "card_number": "4111111111111111",
            "cvv": "123",
            "amount": {"value": "10.00"},
        }

        sanitized = handler._sanitize_payload(payload)
        assert "card_number" not in sanitized
        assert "cvv" not in sanitized
        assert sanitized["id"] == "tr_test"
        assert sanitized["amount"] == {"value": "10.00"}
