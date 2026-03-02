"""Tests for tuition billing: plans, student billing, invoice generation."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant.billing.models import (
    BillingFrequency,
    StudentBilling,
    StudentBillingStatus,
    TuitionInvoice,
    TuitionInvoiceStatus,
    TuitionPlan,
)
from app.modules.tenant.billing.service import TuitionBillingService
from app.modules.tenant.student.models import Student


@pytest_asyncio.fixture
async def test_student(tenant_db_session: AsyncSession) -> Student:
    """Create a real student record to satisfy FK constraints."""
    student = Student(first_name="Billing", last_name="Teststudent")
    tenant_db_session.add(student)
    await tenant_db_session.flush()
    return student


@pytest.mark.asyncio
class TestTuitionPlanCRUD:
    async def test_create_plan(self, tenant_db_session: AsyncSession):
        service = TuitionBillingService(tenant_db_session)
        plan = await service.create_plan({
            "name": "Standaard Les 30 min",
            "amount_cents": 3500,
            "currency": "EUR",
            "frequency": "monthly",
            "lesson_duration_minutes": 30,
        })
        await tenant_db_session.flush()

        assert plan["name"] == "Standaard Les 30 min"
        assert plan["amount_cents"] == 3500
        assert plan["frequency"] == "monthly"
        assert plan["lesson_duration_minutes"] == 30

    async def test_list_plans(self, tenant_db_session: AsyncSession):
        service = TuitionBillingService(tenant_db_session)

        await service.create_plan({
            "name": "Plan A",
            "amount_cents": 3500,
            "currency": "EUR",
            "frequency": "monthly",
            "is_active": True,
        })
        await service.create_plan({
            "name": "Plan B",
            "amount_cents": 5000,
            "currency": "EUR",
            "frequency": "quarterly",
            "is_active": True,
        })
        await service.create_plan({
            "name": "Inactive Plan",
            "amount_cents": 1000,
            "currency": "EUR",
            "frequency": "yearly",
            "is_active": False,
        })
        await tenant_db_session.flush()

        active_plans = await service.list_plans(active_only=True)
        assert len(active_plans) >= 2

        all_plans = await service.list_plans(active_only=False)
        assert len(all_plans) >= 3

    async def test_update_plan(self, tenant_db_session: AsyncSession):
        service = TuitionBillingService(tenant_db_session)
        plan = await service.create_plan({
            "name": "Update Test",
            "amount_cents": 3000,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        updated = await service.update_plan(plan["id"], {"amount_cents": 4000})
        assert updated["amount_cents"] == 4000
        assert updated["name"] == "Update Test"

    async def test_deactivate_plan(self, tenant_db_session: AsyncSession):
        service = TuitionBillingService(tenant_db_session)
        plan = await service.create_plan({
            "name": "Deactivate Test",
            "amount_cents": 2500,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        deactivated = await service.deactivate_plan(plan["id"])
        assert deactivated["is_active"] is False


@pytest.mark.asyncio
class TestStudentBilling:
    async def test_create_student_billing(self, tenant_db_session: AsyncSession, test_student):
        service = TuitionBillingService(tenant_db_session)

        # Create plan first
        plan = await service.create_plan({
            "name": "Test Plan",
            "amount_cents": 3500,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        sb = await service.create_student_billing({
            "student_id": test_student.id,
            "tuition_plan_id": plan["id"],
            "payer_name": "Jan de Vries",
            "payer_email": "jan@example.com",
        })
        await tenant_db_session.flush()

        assert sb["student_id"] == test_student.id
        assert sb["payer_name"] == "Jan de Vries"
        assert sb["status"] == "active"

    async def test_create_billing_with_discount(self, tenant_db_session: AsyncSession, test_student):
        service = TuitionBillingService(tenant_db_session)

        plan = await service.create_plan({
            "name": "Discount Plan",
            "amount_cents": 5000,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        sb = await service.create_student_billing({
            "student_id": test_student.id,
            "tuition_plan_id": plan["id"],
            "payer_name": "Family Discount",
            "payer_email": "family@example.com",
            "discount_percent": 10,
        })
        await tenant_db_session.flush()

        assert sb["discount_percent"] == 10

    async def test_update_student_billing(self, tenant_db_session: AsyncSession, test_student):
        service = TuitionBillingService(tenant_db_session)

        plan = await service.create_plan({
            "name": "Update SB Plan",
            "amount_cents": 3500,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        sb = await service.create_student_billing({
            "student_id": test_student.id,
            "tuition_plan_id": plan["id"],
            "payer_name": "Original Name",
            "payer_email": "original@example.com",
        })
        await tenant_db_session.flush()

        updated = await service.update_student_billing(
            sb["id"], {"payer_name": "Updated Name"}
        )
        assert updated["payer_name"] == "Updated Name"


@pytest.mark.asyncio
class TestInvoiceGeneration:
    async def test_generate_invoice(self, tenant_db_session: AsyncSession, test_student):
        service = TuitionBillingService(tenant_db_session)

        plan = await service.create_plan({
            "name": "Invoice Plan",
            "amount_cents": 3500,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        await service.create_student_billing({
            "student_id": test_student.id,
            "tuition_plan_id": plan["id"],
            "payer_name": "Invoice Test",
            "payer_email": "invoice@example.com",
        })
        await tenant_db_session.flush()

        now = datetime.now(timezone.utc)
        invoices = await service.generate_invoices(
            period_start=now.replace(day=1),
            period_end=(now.replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1),
            tenant_slug="test",
        )
        await tenant_db_session.flush()

        assert len(invoices) >= 1
        inv = invoices[0]
        assert inv["status"] == "draft"
        assert inv["total_cents"] == 3500
        assert inv["invoice_number"].startswith("PS-test-")

    async def test_generate_invoice_with_discount(self, tenant_db_session: AsyncSession, test_student):
        service = TuitionBillingService(tenant_db_session)

        plan = await service.create_plan({
            "name": "Discount Invoice Plan",
            "amount_cents": 10000,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        await service.create_student_billing({
            "student_id": test_student.id,
            "tuition_plan_id": plan["id"],
            "payer_name": "Discount Parent",
            "payer_email": "discount@example.com",
            "discount_percent": 20,
        })
        await tenant_db_session.flush()

        now = datetime.now(timezone.utc)
        invoices = await service.generate_invoices(
            period_start=now.replace(day=1),
            period_end=now.replace(day=28),
            tenant_slug="test",
        )
        await tenant_db_session.flush()

        inv = invoices[0]
        assert inv["subtotal_cents"] == 10000
        assert inv["discount_cents"] == 2000
        assert inv["total_cents"] == 8000

    async def test_send_invoice(self, tenant_db_session: AsyncSession, test_student):
        service = TuitionBillingService(tenant_db_session)

        plan = await service.create_plan({
            "name": "Send Test Plan",
            "amount_cents": 3500,
            "currency": "EUR",
            "frequency": "monthly",
        })
        await tenant_db_session.flush()

        await service.create_student_billing({
            "student_id": test_student.id,
            "tuition_plan_id": plan["id"],
            "payer_name": "Send Test",
            "payer_email": "send@example.com",
        })
        await tenant_db_session.flush()

        now = datetime.now(timezone.utc)
        invoices = await service.generate_invoices(
            period_start=now.replace(day=1),
            period_end=now.replace(day=28),
            tenant_slug="test",
        )
        await tenant_db_session.flush()

        sent = await service.send_invoice(invoices[0]["id"])
        assert sent["status"] == "sent"
        assert sent["sent_at"] is not None
