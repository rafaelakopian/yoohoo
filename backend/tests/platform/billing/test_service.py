"""Tests for BillingService: provider config, plans, subscriptions."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.encryption import decrypt_api_key
from app.modules.platform.billing.models import (
    PaymentProvider,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.billing.service import BillingService
from app.modules.platform.tenant_mgmt.models import Tenant


@pytest_asyncio.fixture
async def billing_tenant_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a real tenant record for billing service tests."""
    tenant = Tenant(
        name="Billing Service Test",
        slug=f"billing-svc-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant.id


@pytest.mark.asyncio
class TestBillingServiceProviders:
    async def test_configure_provider(self, db_session: AsyncSession, billing_tenant_id):
        """Configure a new payment provider for a tenant."""
        service = BillingService(db_session)
        tenant_id = billing_tenant_id

        result = await service.configure_provider(
            tenant_id,
            {
                "provider_type": "mollie",
                "api_key": "test_mollie_key",
                "is_default": True,
            },
        )
        await db_session.flush()

        assert result["provider_type"] == "mollie"
        assert result["is_active"] is True
        assert result["is_default"] is True
        assert result["has_api_key"] is True

        # Verify encryption
        provider = await db_session.execute(
            select(PaymentProvider).where(PaymentProvider.id == result["id"])
        )
        saved = provider.scalar_one()
        assert saved.api_key_encrypted != "test_mollie_key"  # Should be encrypted
        assert decrypt_api_key(saved.api_key_encrypted) == "test_mollie_key"

    async def test_configure_duplicate_provider_raises(self, db_session: AsyncSession, billing_tenant_id):
        """Configuring same provider type twice should raise ConflictError."""
        from app.core.exceptions import ConflictError

        service = BillingService(db_session)
        tenant_id = billing_tenant_id

        await service.configure_provider(
            tenant_id, {"provider_type": "mollie", "api_key": "key1"}
        )
        await db_session.flush()

        with pytest.raises(ConflictError):
            await service.configure_provider(
                tenant_id, {"provider_type": "mollie", "api_key": "key2"}
            )

    async def test_get_providers(self, db_session: AsyncSession, billing_tenant_id):
        """List all providers for a tenant."""
        service = BillingService(db_session)
        tenant_id = billing_tenant_id

        await service.configure_provider(
            tenant_id, {"provider_type": "mollie", "api_key": "key1", "is_default": True}
        )
        await service.configure_provider(
            tenant_id, {"provider_type": "stripe", "api_key": "key2"}
        )
        await db_session.flush()

        providers = await service.get_providers(tenant_id)
        assert len(providers) == 2
        types = {p["provider_type"] for p in providers}
        assert types == {"mollie", "stripe"}


@pytest.mark.asyncio
class TestBillingServicePlans:
    async def test_create_and_list_plans(self, db_session: AsyncSession):
        """Create a plan and verify it appears in list."""
        service = BillingService(db_session)

        plan = await service.create_plan({
            "name": "Starter",
            "slug": f"starter-{uuid.uuid4().hex[:8]}",
            "price_cents": 2900,
            "currency": "EUR",
            "interval": "monthly",
            "is_active": True,
        })
        await db_session.flush()

        plans = await service.list_plans(active_only=True)
        assert any(p["id"] == plan["id"] for p in plans)

    async def test_update_plan(self, db_session: AsyncSession):
        """Update an existing plan."""
        service = BillingService(db_session)

        plan = await service.create_plan({
            "name": "Basic",
            "slug": f"basic-{uuid.uuid4().hex[:8]}",
            "price_cents": 1900,
            "currency": "EUR",
            "interval": "monthly",
        })
        await db_session.flush()

        updated = await service.update_plan(plan["id"], {"price_cents": 2900})
        assert updated["price_cents"] == 2900

    async def test_update_nonexistent_plan_raises(self, db_session: AsyncSession):
        """Updating a non-existent plan should raise NotFoundError."""
        from app.core.exceptions import NotFoundError

        service = BillingService(db_session)
        with pytest.raises(NotFoundError):
            await service.update_plan(uuid.uuid4(), {"name": "Nope"})


@pytest.mark.asyncio
class TestBillingServiceSubscriptions:
    async def test_create_subscription(self, db_session: AsyncSession, billing_tenant_id):
        """Create a subscription for a tenant."""
        service = BillingService(db_session)

        plan = await service.create_plan({
            "name": "Pro",
            "slug": f"pro-{uuid.uuid4().hex[:8]}",
            "price_cents": 5900,
            "currency": "EUR",
            "interval": "monthly",
        })
        await db_session.flush()

        tenant_id = billing_tenant_id
        sub = await service.create_subscription(tenant_id, {"plan_id": plan["id"]})
        await db_session.flush()

        assert sub["tenant_id"] == tenant_id
        assert sub["status"] == "trialing"
        assert sub["plan"]["name"] == "Pro"

    async def test_duplicate_subscription_raises(self, db_session: AsyncSession, billing_tenant_id):
        """Creating two subscriptions for same tenant should raise ConflictError."""
        from app.core.exceptions import ConflictError

        service = BillingService(db_session)

        plan = await service.create_plan({
            "name": "Basic",
            "slug": f"basic-{uuid.uuid4().hex[:8]}",
            "price_cents": 1900,
            "currency": "EUR",
            "interval": "monthly",
        })
        await db_session.flush()

        tenant_id = billing_tenant_id
        await service.create_subscription(tenant_id, {"plan_id": plan["id"]})
        await db_session.flush()

        with pytest.raises(ConflictError):
            await service.create_subscription(tenant_id, {"plan_id": plan["id"]})

    async def test_cancel_subscription(self, db_session: AsyncSession, billing_tenant_id):
        """Cancel a tenant's subscription."""
        service = BillingService(db_session)

        plan = await service.create_plan({
            "name": "Cancel Test",
            "slug": f"cancel-{uuid.uuid4().hex[:8]}",
            "price_cents": 3900,
            "currency": "EUR",
            "interval": "monthly",
        })
        await db_session.flush()

        tenant_id = billing_tenant_id
        await service.create_subscription(tenant_id, {"plan_id": plan["id"]})
        await db_session.flush()

        cancelled = await service.cancel_subscription(tenant_id)
        assert cancelled["status"] == "cancelled"
        assert cancelled["cancelled_at"] is not None
