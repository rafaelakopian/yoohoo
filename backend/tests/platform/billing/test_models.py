"""Tests for platform billing models (CentralBase)."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PlatformPlan,
    PlatformSubscription,
    ProviderType,
    SubscriptionStatus,
    WebhookEvent,
)
from app.modules.platform.tenant_mgmt.models import Tenant


@pytest_asyncio.fixture
async def test_tenant_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a real tenant record to satisfy FK constraints."""
    tenant = Tenant(
        name="Billing Test School",
        slug=f"billing-test-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant.id


@pytest.mark.asyncio
class TestPaymentProvider:
    async def test_create_payment_provider(self, db_session: AsyncSession, test_tenant_id):
        tenant_id = test_tenant_id
        provider = PaymentProvider(
            tenant_id=tenant_id,
            provider_type=ProviderType.mollie,
            is_active=True,
            is_default=True,
            api_key_encrypted="encrypted_key_value",
        )
        db_session.add(provider)
        await db_session.flush()

        result = await db_session.execute(
            select(PaymentProvider).where(PaymentProvider.id == provider.id)
        )
        saved = result.scalar_one()
        assert saved.tenant_id == tenant_id
        assert saved.provider_type == ProviderType.mollie
        assert saved.is_active is True
        assert saved.is_default is True
        assert saved.api_key_encrypted == "encrypted_key_value"

    async def test_provider_types(self):
        assert ProviderType.mollie.value == "mollie"
        assert ProviderType.stripe.value == "stripe"


@pytest.mark.asyncio
class TestPlatformPlan:
    async def test_create_platform_plan(self, db_session: AsyncSession):
        plan = PlatformPlan(
            name="Starter",
            slug=f"starter-{uuid.uuid4().hex[:8]}",
            description="Basic plan",
            price_cents=2900,
            currency="EUR",
            interval="monthly",
            max_students=50,
            max_teachers=5,
            features={"email_notifications": True},
            is_active=True,
            sort_order=1,
        )
        db_session.add(plan)
        await db_session.flush()

        result = await db_session.execute(
            select(PlatformPlan).where(PlatformPlan.id == plan.id)
        )
        saved = result.scalar_one()
        assert saved.name == "Starter"
        assert saved.price_cents == 2900
        assert saved.features == {"email_notifications": True}


@pytest.mark.asyncio
class TestPlatformSubscription:
    async def test_create_subscription(self, db_session: AsyncSession, test_tenant_id):
        # Create a plan first
        plan = PlatformPlan(
            name="Pro",
            slug=f"pro-{uuid.uuid4().hex[:8]}",
            price_cents=5900,
            currency="EUR",
            interval="monthly",
        )
        db_session.add(plan)
        await db_session.flush()

        tenant_id = test_tenant_id
        sub = PlatformSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=SubscriptionStatus.trialing,
        )
        db_session.add(sub)
        await db_session.flush()

        result = await db_session.execute(
            select(PlatformSubscription).where(PlatformSubscription.id == sub.id)
        )
        saved = result.scalar_one()
        assert saved.status == SubscriptionStatus.trialing
        assert saved.tenant_id == tenant_id

    async def test_subscription_statuses(self):
        assert SubscriptionStatus.trialing.value == "trialing"
        assert SubscriptionStatus.active.value == "active"
        assert SubscriptionStatus.past_due.value == "past_due"
        assert SubscriptionStatus.cancelled.value == "cancelled"
        assert SubscriptionStatus.expired.value == "expired"


@pytest.mark.asyncio
class TestInvoice:
    async def test_create_invoice(self, db_session: AsyncSession, test_tenant_id):
        tenant_id = test_tenant_id
        invoice = Invoice(
            invoice_number=f"PS-TEST-2026-{uuid.uuid4().hex[:4]}",
            invoice_type=InvoiceType.platform,
            tenant_id=tenant_id,
            recipient_name="Test School",
            recipient_email="school@example.com",
            subtotal_cents=5900,
            tax_cents=1239,
            total_cents=7139,
            currency="EUR",
            status=InvoiceStatus.draft,
            line_items=[{"description": "Pro Plan - March 2026", "amount_cents": 5900}],
        )
        db_session.add(invoice)
        await db_session.flush()

        result = await db_session.execute(
            select(Invoice).where(Invoice.id == invoice.id)
        )
        saved = result.scalar_one()
        assert saved.invoice_type == InvoiceType.platform
        assert saved.total_cents == 7139
        assert saved.status == InvoiceStatus.draft

    async def test_invoice_types(self):
        assert InvoiceType.platform.value == "platform"
        assert InvoiceType.tuition.value == "tuition"


@pytest.mark.asyncio
class TestPayment:
    async def test_create_payment(self, db_session: AsyncSession, test_tenant_id):
        tenant_id = test_tenant_id
        # Create invoice first
        invoice = Invoice(
            invoice_number=f"PS-PAY-{uuid.uuid4().hex[:6]}",
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
            provider_payment_id="tr_test123",
            amount_cents=7139,
            currency="EUR",
            status=PaymentStatus.pending,
            payment_method="ideal",
            idempotency_key=f"idem-{uuid.uuid4().hex}",
        )
        db_session.add(payment)
        await db_session.flush()

        result = await db_session.execute(
            select(Payment).where(Payment.id == payment.id)
        )
        saved = result.scalar_one()
        assert saved.provider_payment_id == "tr_test123"
        assert saved.payment_method == "ideal"
        assert saved.status == PaymentStatus.pending


@pytest.mark.asyncio
class TestWebhookEvent:
    async def test_create_webhook_event(self, db_session: AsyncSession):
        event = WebhookEvent(
            provider_type=ProviderType.mollie,
            provider_event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="payment.paid",
            payload={"id": "tr_test123"},
            processed=False,
        )
        db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(WebhookEvent).where(WebhookEvent.id == event.id)
        )
        saved = result.scalar_one()
        assert saved.event_type == "payment.paid"
        assert saved.processed is False
        assert saved.payload == {"id": "tr_test123"}
