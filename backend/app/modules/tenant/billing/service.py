"""Tuition billing service: plans, student billing, invoice generation."""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.tenant.billing.models import (
    StudentBilling,
    StudentBillingStatus,
    TuitionInvoice,
    TuitionInvoiceStatus,
    TuitionPayment,
    TuitionPlan,
)

logger = structlog.get_logger()


class TuitionBillingService:
    """Service for tenant-level tuition billing."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Tuition Plans ───

    async def list_plans(self, active_only: bool = True) -> list[dict]:
        query = select(TuitionPlan).order_by(TuitionPlan.name)
        if active_only:
            query = query.where(TuitionPlan.is_active == True)  # noqa: E712
        result = await self.db.execute(query)
        return [self._plan_to_dict(p) for p in result.scalars().all()]

    async def get_plan(self, plan_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(TuitionPlan).where(TuitionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundError("TuitionPlan", plan_id)
        return self._plan_to_dict(plan)

    async def create_plan(self, data: dict) -> dict:
        plan = TuitionPlan(**data)
        self.db.add(plan)
        await self.db.flush()
        return self._plan_to_dict(plan)

    async def update_plan(self, plan_id: uuid.UUID, data: dict) -> dict:
        result = await self.db.execute(
            select(TuitionPlan).where(TuitionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundError("TuitionPlan", plan_id)

        for key, value in data.items():
            if value is not None:
                setattr(plan, key, value)
        await self.db.flush()
        await self.db.refresh(plan)
        return self._plan_to_dict(plan)

    async def deactivate_plan(self, plan_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(TuitionPlan).where(TuitionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundError("TuitionPlan", plan_id)

        plan.is_active = False
        await self.db.flush()
        await self.db.refresh(plan)
        return self._plan_to_dict(plan)

    # ─── Student Billing ───

    async def list_student_billing(
        self,
        student_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        query = select(StudentBilling)
        count_query = select(func.count(StudentBilling.id))

        if student_id:
            query = query.where(StudentBilling.student_id == student_id)
            count_query = count_query.where(StudentBilling.student_id == student_id)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(StudentBilling.created_at.desc()).offset(skip).limit(limit)
        )
        items = [self._student_billing_to_dict(sb) for sb in result.scalars().all()]
        return items, total

    async def get_student_billing(self, student_id: uuid.UUID) -> dict | None:
        result = await self.db.execute(
            select(StudentBilling).where(
                StudentBilling.student_id == student_id,
                StudentBilling.status == StudentBillingStatus.active,
            )
        )
        sb = result.scalar_one_or_none()
        if not sb:
            return None
        return self._student_billing_to_dict(sb)

    async def create_student_billing(self, data: dict) -> dict:
        # Verify plan exists
        plan_result = await self.db.execute(
            select(TuitionPlan).where(TuitionPlan.id == data["tuition_plan_id"])
        )
        if not plan_result.scalar_one_or_none():
            raise NotFoundError("TuitionPlan", data["tuition_plan_id"])

        sb = StudentBilling(**data)
        self.db.add(sb)
        await self.db.flush()
        return self._student_billing_to_dict(sb)

    async def update_student_billing(
        self, billing_id: uuid.UUID, data: dict
    ) -> dict:
        result = await self.db.execute(
            select(StudentBilling).where(StudentBilling.id == billing_id)
        )
        sb = result.scalar_one_or_none()
        if not sb:
            raise NotFoundError("StudentBilling", billing_id)

        for key, value in data.items():
            if value is not None:
                setattr(sb, key, value)
        await self.db.flush()
        await self.db.refresh(sb)
        return self._student_billing_to_dict(sb)

    # ─── Invoice Generation ───

    async def generate_invoices(
        self,
        period_start: datetime,
        period_end: datetime,
        tenant_slug: str,
        student_billing_ids: list[uuid.UUID] | None = None,
    ) -> list[dict]:
        """Generate tuition invoices for a billing period."""
        query = select(StudentBilling).where(
            StudentBilling.status == StudentBillingStatus.active
        )
        if student_billing_ids:
            query = query.where(StudentBilling.id.in_(student_billing_ids))

        result = await self.db.execute(query)
        billings = result.scalars().all()

        invoices = []
        skipped = 0
        for sb in billings:
            # Idempotency: skip if invoice already exists for this billing+period
            existing = await self.db.execute(
                select(TuitionInvoice.id).where(
                    TuitionInvoice.student_billing_id == sb.id,
                    TuitionInvoice.period_start == period_start,
                    TuitionInvoice.period_end == period_end,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            # Get the plan for amount calculation
            plan_result = await self.db.execute(
                select(TuitionPlan).where(TuitionPlan.id == sb.tuition_plan_id)
            )
            plan = plan_result.scalar_one_or_none()
            if not plan:
                continue

            # Calculate amounts
            subtotal = sb.custom_amount_cents if sb.custom_amount_cents else plan.amount_cents
            discount = 0
            if sb.discount_percent:
                discount = int(subtotal * sb.discount_percent / 100)
            total = subtotal - discount

            # Get student name (from student_id, we use payer info as fallback)
            student_name = sb.payer_name  # Will be enriched in future with student lookup

            # Create invoice with retry on invoice_number collision (concurrent requests)
            invoice = await self._create_invoice_with_seq_retry(
                sb=sb,
                plan=plan,
                tenant_slug=tenant_slug,
                period_start=period_start,
                period_end=period_end,
                subtotal=subtotal,
                discount=discount,
                total=total,
                student_name=student_name,
            )
            invoices.append(self._invoice_to_dict(invoice))

        logger.info(
            "billing.invoices_generated",
            count=len(invoices),
            skipped=skipped,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
        )
        return invoices

    async def _next_invoice_number(self, tenant_slug: str, year: int) -> str:
        """Get next sequential invoice number using max() of existing numbers."""
        prefix = f"{settings.billing_invoice_prefix}-{tenant_slug}-{year}-"
        max_result = await self.db.execute(
            select(func.max(TuitionInvoice.invoice_number)).where(
                TuitionInvoice.invoice_number.like(f"{prefix}%")
            )
        )
        last_number = max_result.scalar()
        if last_number:
            last_seq = int(last_number.rsplit("-", 1)[1])
            seq = last_seq + 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    async def _create_invoice_with_seq_retry(
        self,
        sb: StudentBilling,
        plan: TuitionPlan,
        tenant_slug: str,
        period_start: datetime,
        period_end: datetime,
        subtotal: int,
        discount: int,
        total: int,
        student_name: str,
        max_retries: int = 3,
    ) -> TuitionInvoice:
        """Create invoice with retry on invoice_number collision.

        If two concurrent requests get the same max()+1, the unique constraint
        on invoice_number causes an IntegrityError. We catch it, rollback the
        failed flush, re-query max(), and retry.
        """
        for attempt in range(max_retries):
            invoice_number = await self._next_invoice_number(
                tenant_slug, period_start.year
            )
            invoice = TuitionInvoice(
                invoice_number=invoice_number,
                student_billing_id=sb.id,
                payer_name=sb.payer_name,
                payer_email=sb.payer_email,
                student_name=student_name,
                period_start=period_start,
                period_end=period_end,
                subtotal_cents=subtotal,
                discount_cents=discount,
                total_cents=total,
                currency=plan.currency,
                status=TuitionInvoiceStatus.draft,
                description=f"{plan.name} - {period_start.strftime('%B %Y')}",
                line_items=[
                    {
                        "description": plan.name,
                        "amount_cents": subtotal,
                        "discount_cents": discount,
                    }
                ],
                due_date=period_end + timedelta(days=settings.billing_invoice_due_days),
            )
            self.db.add(invoice)
            try:
                await self.db.flush()
                return invoice
            except IntegrityError as e:
                await self.db.rollback()
                # Extract constraint name from the DB driver exception
                constraint = getattr(e.orig, "constraint_name", None) or ""
                if not constraint:
                    # Fallback: parse from error message
                    constraint = str(e.orig) if e.orig else str(e)
                if "uq_invoice_billing_period" in constraint:
                    # Duplicate billing+period — idempotency race, skip
                    raise ConflictError(
                        "Invoice already exists for this billing period"
                    ) from e
                if "invoice_number" not in constraint and attempt == max_retries - 1:
                    raise
                logger.warning(
                    "billing.invoice_number_collision",
                    invoice_number=invoice_number,
                    attempt=attempt + 1,
                )

        raise ConflictError("Failed to generate unique invoice number after retries")

    async def list_invoices(
        self,
        student_billing_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        query = select(TuitionInvoice)
        count_query = select(func.count(TuitionInvoice.id))
        filters = []

        if student_billing_id:
            filters.append(TuitionInvoice.student_billing_id == student_billing_id)
        if status:
            filters.append(TuitionInvoice.status == status)

        for f in filters:
            query = query.where(f)
            count_query = count_query.where(f)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(TuitionInvoice.created_at.desc()).offset(skip).limit(limit)
        )
        items = [self._invoice_to_dict(inv) for inv in result.scalars().all()]
        return items, total

    async def get_invoice(self, invoice_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(TuitionInvoice).where(TuitionInvoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("TuitionInvoice", invoice_id)
        return self._invoice_to_dict(invoice)

    async def send_invoice(self, invoice_id: uuid.UUID) -> dict:
        """Mark invoice as sent (email sending handled by notification module)."""
        result = await self.db.execute(
            select(TuitionInvoice).where(TuitionInvoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("TuitionInvoice", invoice_id)

        invoice.status = TuitionInvoiceStatus.sent
        invoice.sent_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(invoice)

        logger.info("billing.invoice_sent", invoice_id=str(invoice_id))
        return self._invoice_to_dict(invoice)

    # ─── Dict Helpers ───

    @staticmethod
    def _plan_to_dict(plan: TuitionPlan) -> dict:
        return {
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "amount_cents": plan.amount_cents,
            "currency": plan.currency,
            "frequency": plan.frequency.value if hasattr(plan.frequency, "value") else plan.frequency,
            "lesson_duration_minutes": plan.lesson_duration_minutes,
            "is_active": plan.is_active,
            "extra_config": plan.extra_config,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

    @staticmethod
    def _student_billing_to_dict(sb: StudentBilling) -> dict:
        return {
            "id": sb.id,
            "student_id": sb.student_id,
            "tuition_plan_id": sb.tuition_plan_id,
            "payer_user_id": sb.payer_user_id,
            "payer_name": sb.payer_name,
            "payer_email": sb.payer_email,
            "status": sb.status.value if hasattr(sb.status, "value") else sb.status,
            "custom_amount_cents": sb.custom_amount_cents,
            "discount_percent": sb.discount_percent,
            "billing_start_date": sb.billing_start_date,
            "billing_end_date": sb.billing_end_date,
            "notes": sb.notes,
            "created_at": sb.created_at,
            "updated_at": sb.updated_at,
        }

    @staticmethod
    def _invoice_to_dict(inv: TuitionInvoice) -> dict:
        return {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "student_billing_id": inv.student_billing_id,
            "central_invoice_id": inv.central_invoice_id,
            "payer_name": inv.payer_name,
            "payer_email": inv.payer_email,
            "student_name": inv.student_name,
            "period_start": inv.period_start,
            "period_end": inv.period_end,
            "subtotal_cents": inv.subtotal_cents,
            "discount_cents": inv.discount_cents,
            "total_cents": inv.total_cents,
            "currency": inv.currency,
            "status": inv.status.value if hasattr(inv.status, "value") else inv.status,
            "description": inv.description,
            "line_items": inv.line_items,
            "due_date": inv.due_date,
            "sent_at": inv.sent_at,
            "paid_at": inv.paid_at,
            "checkout_url": inv.checkout_url,
            "created_at": inv.created_at,
            "updated_at": inv.updated_at,
        }
