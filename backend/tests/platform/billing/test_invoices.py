"""Tests for invoice endpoints: dunning info in response, mark-paid."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.models import Invoice, InvoiceStatus, InvoiceType
from app.modules.platform.tenant_mgmt.models import Tenant


@pytest_asyncio.fixture
async def invoice_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(
        name="Invoice Test Tenant",
        slug=f"inv-test-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def open_invoice(db_session: AsyncSession, invoice_tenant: Tenant) -> Invoice:
    inv = Invoice(
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:6]}",
        invoice_type=InvoiceType.platform,
        tenant_id=invoice_tenant.id,
        recipient_name="Test Klant",
        recipient_email="klant@test.nl",
        subtotal_cents=10000,
        tax_cents=2100,
        total_cents=12100,
        currency="EUR",
        status=InvoiceStatus.open,
        due_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        extra_data={
            "dunning_reminder_count": 2,
            "dunning_last_sent_at": "2025-02-15T10:00:00+00:00",
        },
    )
    db_session.add(inv)
    await db_session.flush()
    return inv


@pytest_asyncio.fixture
async def paid_invoice(db_session: AsyncSession, invoice_tenant: Tenant) -> Invoice:
    inv = Invoice(
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:6]}",
        invoice_type=InvoiceType.platform,
        tenant_id=invoice_tenant.id,
        recipient_name="Betaalde Klant",
        recipient_email="betaald@test.nl",
        subtotal_cents=5000,
        tax_cents=1050,
        total_cents=6050,
        currency="EUR",
        status=InvoiceStatus.paid,
        paid_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.flush()
    return inv


@pytest.mark.asyncio
class TestInvoiceDunningInfo:
    async def test_invoice_response_includes_dunning_fields(
        self, client: AsyncClient, auth_headers: dict, open_invoice: Invoice,
    ):
        """InvoiceResponse should include dunning_count and dunning_last_sent_at."""
        resp = await client.get(
            f"/api/v1/platform/billing/invoices/{open_invoice.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dunning_count"] == 2
        assert data["dunning_last_sent_at"] is not None
        assert "2025-02-15" in data["dunning_last_sent_at"]

    async def test_invoice_response_dunning_defaults(
        self, client: AsyncClient, auth_headers: dict, paid_invoice: Invoice,
    ):
        """Invoice without dunning data should have defaults (0, null)."""
        resp = await client.get(
            f"/api/v1/platform/billing/invoices/{paid_invoice.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dunning_count"] == 0
        assert data["dunning_last_sent_at"] is None


@pytest.mark.asyncio
class TestMarkInvoicePaid:
    async def test_mark_paid_success(
        self, client: AsyncClient, auth_headers: dict, open_invoice: Invoice,
    ):
        """Should mark an open invoice as paid."""
        resp = await client.post(
            f"/api/v1/platform/billing/invoices/{open_invoice.id}/mark-paid",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["paid_at"] is not None

    async def test_mark_paid_already_paid(
        self, client: AsyncClient, auth_headers: dict, paid_invoice: Invoice,
    ):
        """Should return 409 for an already paid invoice."""
        resp = await client.post(
            f"/api/v1/platform/billing/invoices/{paid_invoice.id}/mark-paid",
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_mark_paid_not_found(
        self, client: AsyncClient, auth_headers: dict,
    ):
        """Should return 404 for nonexistent invoice."""
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/platform/billing/invoices/{fake_id}/mark-paid",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_mark_paid_requires_permission(
        self, client: AsyncClient, open_invoice: Invoice,
    ):
        """Should require authentication."""
        resp = await client.post(
            f"/api/v1/platform/billing/invoices/{open_invoice.id}/mark-paid",
        )
        assert resp.status_code == 401

    async def test_mark_paid_draft_rejected(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
        invoice_tenant: Tenant,
    ):
        """Should reject marking a draft invoice as paid."""
        inv = Invoice(
            invoice_number=f"INV-DRAFT-{uuid.uuid4().hex[:6]}",
            invoice_type=InvoiceType.platform,
            tenant_id=invoice_tenant.id,
            recipient_name="Draft Klant",
            recipient_email="draft@test.nl",
            subtotal_cents=1000,
            tax_cents=210,
            total_cents=1210,
            currency="EUR",
            status=InvoiceStatus.draft,
        )
        db_session.add(inv)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/platform/billing/invoices/{inv.id}/mark-paid",
            headers=auth_headers,
        )
        assert resp.status_code == 409
