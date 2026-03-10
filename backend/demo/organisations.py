"""Demo organisation definitions and creation logic."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.platform.auth.models import (
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.auth.permissions_setup import create_default_groups
from app.modules.platform.billing.models import (
    PlanInterval,
    PlatformPlan,
    PlatformSubscription,
)
from app.modules.platform.billing.plan_features import FeatureConfig, PlanFeatures
from app.modules.platform.tenant_mgmt.db_provisioner import create_tenant_database
from app.modules.platform.tenant_mgmt.models import Tenant, TenantSettings


# ---------------------------------------------------------------------------
# Demo plan definitions
# ---------------------------------------------------------------------------

DEMO_PLANS = [
    {
        "name": "Basis",
        "slug": "demo-basis",
        "price_cents": 1999,
        "currency": "EUR",
        "interval": PlanInterval.monthly,
        "features": PlanFeatures(
            billing=FeatureConfig(enabled=False, trial_days=14),
            reporting=FeatureConfig(enabled=False, trial_days=14),
        ).model_dump(),
    },
    {
        "name": "Uitgebreid",
        "slug": "demo-uitgebreid",
        "price_cents": 2999,
        "currency": "EUR",
        "interval": PlanInterval.monthly,
        "features": PlanFeatures(
            billing=FeatureConfig(enabled=True, trial_days=14),
            collaborations=FeatureConfig(enabled=True, trial_days=14),
            reporting=FeatureConfig(enabled=False, trial_days=14),
        ).model_dump(),
    },
]


# ---------------------------------------------------------------------------
# Demo organisation definitions
# ---------------------------------------------------------------------------

DEMO_ORGS = [
    {
        "name": "Muziekschool De Klankvlek",
        "slug": "demo-klankvlek",
        "plan_slug": "demo-basis",
        "owner_email": "klankvlek-owner@demo.yoohoo",
        "owner_name": "Marieke de Wit",
        "student_count": 12,
    },
    {
        "name": "Pianostudio Hartman",
        "slug": "demo-hartman",
        "plan_slug": "demo-uitgebreid",
        "owner_email": "hartman-owner@demo.yoohoo",
        "owner_name": "Jan Hartman",
        "student_count": 8,
    },
    {
        "name": "Muziekatelier Vos",
        "slug": "demo-vos",
        "plan_slug": "demo-basis",
        "owner_email": "vos-owner@demo.yoohoo",
        "owner_name": "Linda Vos",
        "student_count": 6,
    },
]


def _log(msg: str) -> None:
    import sys
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Creation helpers
# ---------------------------------------------------------------------------


async def create_demo_plans(db: AsyncSession) -> dict[str, PlatformPlan]:
    """Create demo plans (idempotent — skips if slug exists)."""
    plans: dict[str, PlatformPlan] = {}
    for plan_def in DEMO_PLANS:
        existing = await db.execute(
            select(PlatformPlan).where(PlatformPlan.slug == plan_def["slug"])
        )
        plan = existing.scalar_one_or_none()
        if plan:
            plans[plan_def["slug"]] = plan
            continue

        plan = PlatformPlan(
            name=plan_def["name"],
            slug=plan_def["slug"],
            price_cents=plan_def["price_cents"],
            currency=plan_def["currency"],
            interval=plan_def["interval"],
            features=plan_def["features"],
            is_active=True,
            sort_order=0,
        )
        db.add(plan)
        await db.flush()
        plans[plan_def["slug"]] = plan
        _log(f"  Plan '{plan_def['name']}' aangemaakt")

    return plans


async def create_demo_org(
    db: AsyncSession,
    org_def: dict,
    plans: dict[str, PlatformPlan],
    password: str,
) -> tuple[Tenant, User, dict[str, "PermissionGroup"]]:
    """Create one demo organisation: owner + tenant + provision + subscription + groups."""
    slug = org_def["slug"]

    # 1. Owner user
    owner = User(
        email=org_def["owner_email"],
        hashed_password=hash_password(password),
        full_name=org_def["owner_name"],
        is_active=True,
        is_superadmin=False,
        email_verified=True,
    )
    db.add(owner)
    await db.flush()

    # 2. Tenant
    tenant = Tenant(
        name=org_def["name"],
        slug=slug,
        owner_id=owner.id,
        is_active=True,
        is_provisioned=False,
    )
    db.add(tenant)
    await db.flush()

    # 3. Tenant settings
    db.add(TenantSettings(tenant_id=tenant.id, org_name=org_def["name"]))
    await db.flush()

    # 4. Owner membership
    db.add(TenantMembership(
        user_id=owner.id, tenant_id=tenant.id, is_active=True, membership_type="full",
    ))
    await db.flush()

    # 5. Default permission groups
    groups = await create_default_groups(db, tenant.id)

    # 6. Assign owner to beheerder
    if "beheerder" in groups:
        db.add(UserGroupAssignment(user_id=owner.id, group_id=groups["beheerder"].id))
        await db.flush()

    await db.commit()

    # 7. Provision tenant database (outside session — like seed.py)
    _log(f"  Provisioning database '{slug}'...")
    await create_tenant_database(slug)

    # Re-open session to mark provisioned
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one()
    tenant.is_provisioned = True
    await db.commit()

    # 8. Subscription
    plan = plans[org_def["plan_slug"]]
    sub = PlatformSubscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
    )
    db.add(sub)
    await db.commit()

    _log(f"  Org '{org_def['name']}' aangemaakt ({slug})")
    return tenant, owner, groups
