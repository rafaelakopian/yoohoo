"""Tests for payment flow: create_invoice_payment, webhook auto-resume, platform-invoices endpoint."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.modules.platform.auth.models import User
from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    Payment,
    PaymentStatus,
    PlanInterval,
    PlatformPlan,
    PlatformSubscription,
    ProviderType,
    SubscriptionStatus,
)
from app.modules.platform.billing.plan_features import FeatureConfig, PlanFeatures
from app.modules.platform.billing.providers.base import PaymentResult
from app.modules.platform.billing.service import BillingService
from app.modules.platform.billing.subscription_guard import clear_sub_status_cache
from app.modules.platform.billing.webhooks.handler import WebhookHandler
from app.modules.platform.tenant_mgmt.models import Tenant
from tests.conftest import TEST_TENANT_UUID


# ─── Helpers ───


async def _ensure_test_tenant(db, tenant_id=TEST_TENANT_UUID):
    """Ensure the test tenant exists in DB."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if result.scalar_one_or_none():
        return
    owner = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@test.nl",
        hashed_password="hashed",
        full_name="Test Owner",
        is_active=True,
        email_verified=True,
    )
    db.add(owner)
    await db.flush()
    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug="test",
        is_active=True,
        is_provisioned=True,
        owner_id=owner.id,
    )
    db.add(tenant)
    await db.flush()


async def _create_plan(db, *, price_cents=1999):
    """Create a platform plan."""
    unique = uuid.uuid4().hex[:8]
    features = PlanFeatures(
        billing=FeatureConfig(enabled=True, trial_days=14),
    ).model_dump()
    plan = PlatformPlan(
        name=f"Plan {unique}",
        slug=f"plan-{unique}",
        price_cents=price_cents,
        currency="EUR",
        interval=PlanInterval.monthly,
        is_active=True,
        features=features,
    )
    db.add(plan)
    await db.flush()
    return plan


async def _create_invoice(db, *, status=InvoiceStatus.open, invoice_type=InvoiceType.platform,
                           tenant_id=TEST_TENANT_UUID, total_cents=1999):
    """Create an invoice."""
    invoice = Invoice(
        invoice_number=f"PS-PLT-{uuid.uuid4().hex[:8]}",
        invoice_type=invoice_type,
        tenant_id=tenant_id,
        recipient_name="Test",
        recipient_email="test@test.nl",
        subtotal_cents=round(total_cents / 1.21),
        tax_cents=total_cents - round(total_cents / 1.21),
        total_cents=total_cents,
        currency="EUR",
        status=status,
        description="Abonnement Test",
    )
    db.add(invoice)
    await db.flush()
    return invoice


async def _create_paused_subscription(db, plan, *, tenant_id=TEST_TENANT_UUID):
    """Create a paused subscription."""
    paused_at = datetime.now(timezone.utc) - timedelta(days=30)
    sub = PlatformSubscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        status=SubscriptionStatus.paused,
        extra_data={"paused_at": paused_at.isoformat()},
    )
    db.add(sub)
    await db.flush()
    return sub


@pytest.fixture(autouse=True)
def _clear_sub_cache():
    """Clear subscription status cache between tests."""
    clear_sub_status_cache()
    yield
    clear_sub_status_cache()


# ─── Service: create_invoice_payment ───


@pytest.mark.asyncio
async def test_create_invoice_payment_returns_checkout_url(db_session):
    """create_invoice_payment should return a checkout_url for an open invoice."""
    await _ensure_test_tenant(db_session)
    invoice = await _create_invoice(db_session, status=InvoiceStatus.open)

    mock_result = PaymentResult(
        provider_payment_id="tr_mock_123",
        status="pending",
        checkout_url="https://checkout.mollie.com/test",
    )

    service = BillingService(db_session)

    with patch.object(service, "get_provider_instance") as mock_provider:
        provider_instance = AsyncMock()
        provider_instance.create_checkout_session = AsyncMock(return_value=mock_result)
        mock_provider.return_value = provider_instance

        # Need to detect provider type correctly
        from app.modules.platform.billing.providers.mollie import MollieProvider
        provider_instance.__class__ = MollieProvider

        result = await service.create_invoice_payment(
            tenant_id=TEST_TENANT_UUID,
            invoice_id=invoice.id,
            tenant_slug="test",
        )

    assert result["checkout_url"] == "https://checkout.mollie.com/test"
    assert result["invoice_number"] == invoice.invoice_number
    assert result["payment_id"] is not None


@pytest.mark.asyncio
async def test_create_invoice_payment_rejects_paid_invoice(db_session):
    """create_invoice_payment should raise ConflictError for already-paid invoice."""
    await _ensure_test_tenant(db_session)
    invoice = await _create_invoice(db_session, status=InvoiceStatus.paid)

    from app.core.exceptions import ConflictError

    service = BillingService(db_session)
    with pytest.raises(ConflictError):
        await service.create_invoice_payment(
            tenant_id=TEST_TENANT_UUID,
            invoice_id=invoice.id,
        )


@pytest.mark.asyncio
async def test_create_invoice_payment_rejects_no_provider(db_session):
    """create_invoice_payment should raise ConflictError when no provider is configured."""
    await _ensure_test_tenant(db_session)
    invoice = await _create_invoice(db_session, status=InvoiceStatus.open)

    service = BillingService(db_session)

    from app.core.exceptions import ConflictError

    # No PaymentProvider configured → get_provider_instance raises NotFoundError
    # → create_invoice_payment converts to ConflictError with helpful message
    with pytest.raises(ConflictError, match="Geen betaalprovider"):
        await service.create_invoice_payment(
            tenant_id=TEST_TENANT_UUID,
            invoice_id=invoice.id,
        )


# ─── Webhook: auto-resume ───


@pytest.mark.asyncio
async def test_webhook_auto_resumes_paused_subscription(db_session):
    """Webhook payment.paid should auto-resume subscription when all invoices are paid."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session)
    await _create_paused_subscription(db_session, plan)

    # Create a single open invoice + payment
    invoice = await _create_invoice(db_session, status=InvoiceStatus.open)
    payment = Payment(
        invoice_id=invoice.id,
        tenant_id=TEST_TENANT_UUID,
        provider_type=ProviderType.mollie,
        provider_payment_id="tr_auto_resume",
        amount_cents=1999,
        status=PaymentStatus.pending,
    )
    db_session.add(payment)
    await db_session.flush()

    # Process payment.paid webhook
    handler = WebhookHandler(db_session)
    await handler.process_event(
        provider_type="mollie",
        event_id=f"evt_{uuid.uuid4().hex[:12]}",
        event_type="payment.paid",
        payment_id="tr_auto_resume",
        payload={"id": "tr_auto_resume"},
    )
    await db_session.flush()

    # Verify subscription is now active
    result = await db_session.execute(
        select(PlatformSubscription).where(
            PlatformSubscription.tenant_id == TEST_TENANT_UUID
        )
    )
    sub = result.scalar_one()
    assert sub.status == SubscriptionStatus.active


@pytest.mark.asyncio
async def test_webhook_does_not_resume_with_open_invoices(db_session):
    """Webhook should NOT resume if there are still open invoices."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session)
    await _create_paused_subscription(db_session, plan)

    # Create TWO open invoices, only one gets paid
    invoice1 = await _create_invoice(db_session, status=InvoiceStatus.open)
    await _create_invoice(db_session, status=InvoiceStatus.open)  # Still open

    payment = Payment(
        invoice_id=invoice1.id,
        tenant_id=TEST_TENANT_UUID,
        provider_type=ProviderType.mollie,
        provider_payment_id="tr_partial_pay",
        amount_cents=1999,
        status=PaymentStatus.pending,
    )
    db_session.add(payment)
    await db_session.flush()

    handler = WebhookHandler(db_session)
    await handler.process_event(
        provider_type="mollie",
        event_id=f"evt_{uuid.uuid4().hex[:12]}",
        event_type="payment.paid",
        payment_id="tr_partial_pay",
        payload={"id": "tr_partial_pay"},
    )
    await db_session.flush()

    # Subscription should still be paused
    result = await db_session.execute(
        select(PlatformSubscription).where(
            PlatformSubscription.tenant_id == TEST_TENANT_UUID
        )
    )
    sub = result.scalar_one()
    assert sub.status == SubscriptionStatus.paused


@pytest.mark.asyncio
async def test_webhook_does_not_resume_active_subscription(db_session):
    """Webhook should NOT resume if subscription is already active."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session)

    # Create ACTIVE subscription (not paused)
    sub = PlatformSubscription(
        tenant_id=TEST_TENANT_UUID,
        plan_id=plan.id,
        status=SubscriptionStatus.active,
    )
    db_session.add(sub)
    await db_session.flush()

    invoice = await _create_invoice(db_session, status=InvoiceStatus.open)
    payment = Payment(
        invoice_id=invoice.id,
        tenant_id=TEST_TENANT_UUID,
        provider_type=ProviderType.mollie,
        provider_payment_id="tr_already_active",
        amount_cents=1999,
        status=PaymentStatus.pending,
    )
    db_session.add(payment)
    await db_session.flush()

    handler = WebhookHandler(db_session)
    await handler.process_event(
        provider_type="mollie",
        event_id=f"evt_{uuid.uuid4().hex[:12]}",
        event_type="payment.paid",
        payment_id="tr_already_active",
        payload={"id": "tr_already_active"},
    )
    await db_session.flush()

    # Subscription should still be active (no crash, no change)
    result = await db_session.execute(
        select(PlatformSubscription).where(
            PlatformSubscription.tenant_id == TEST_TENANT_UUID
        )
    )
    sub_result = result.scalar_one()
    assert sub_result.status == SubscriptionStatus.active


# ─── API: platform-invoices ───


@pytest.mark.asyncio
async def test_platform_invoices_returns_only_platform(
    tenant_client, tenant_auth_headers, db_session
):
    """GET /org/{slug}/billing/platform-invoices should return only platform invoices."""
    await _ensure_test_tenant(db_session)
    await _create_invoice(db_session, invoice_type=InvoiceType.platform)
    await _create_invoice(db_session, invoice_type=InvoiceType.tuition)

    resp = await tenant_client.get(
        "/api/v1/org/test/billing/platform-invoices",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(inv["invoice_type"] == "platform" for inv in data)


@pytest.mark.asyncio
async def test_platform_invoices_filters_by_status(
    tenant_client, tenant_auth_headers, db_session
):
    """GET /org/{slug}/billing/platform-invoices?status=open should filter correctly."""
    await _ensure_test_tenant(db_session)
    await _create_invoice(db_session, status=InvoiceStatus.open)
    await _create_invoice(db_session, status=InvoiceStatus.paid)

    resp = await tenant_client.get(
        "/api/v1/org/test/billing/platform-invoices?status=open",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(inv["status"] == "open" for inv in data)


# ─── API: pay invoice ───


@pytest.mark.asyncio
async def test_pay_invoice_endpoint(
    tenant_client, tenant_auth_headers, db_session
):
    """POST /org/{slug}/billing/invoices/{id}/pay should return checkout_url."""
    await _ensure_test_tenant(db_session)
    invoice = await _create_invoice(db_session, status=InvoiceStatus.open)

    mock_result = PaymentResult(
        provider_payment_id="tr_endpoint_test",
        status="pending",
        checkout_url="https://checkout.mollie.com/endpoint-test",
    )

    with patch(
        "app.modules.platform.billing.service.BillingService.get_provider_instance"
    ) as mock_provider:
        from app.modules.platform.billing.providers.mollie import MollieProvider

        provider_instance = AsyncMock(spec=MollieProvider)
        provider_instance.create_checkout_session = AsyncMock(return_value=mock_result)
        mock_provider.return_value = provider_instance

        resp = await tenant_client.post(
            f"/api/v1/org/test/billing/invoices/{invoice.id}/pay",
            headers=tenant_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["checkout_url"] == "https://checkout.mollie.com/endpoint-test"
    assert data["invoice_number"] == invoice.invoice_number


@pytest.mark.asyncio
async def test_pay_invoice_unauthenticated(tenant_client, db_session):
    """POST /org/{slug}/billing/invoices/{id}/pay without auth should return 401."""
    fake_id = uuid.uuid4()
    resp = await tenant_client.post(
        f"/api/v1/org/test/billing/invoices/{fake_id}/pay",
    )
    assert resp.status_code == 401
