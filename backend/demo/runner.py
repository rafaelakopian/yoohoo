"""Demo seed runner — orchestrates creation and teardown of all demo data."""

import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.central import async_session_factory
from app.db.tenant import tenant_db_manager
from app.modules.platform.auth.models import User
from app.modules.platform.billing.models import PlatformPlan
from app.modules.platform.tenant_mgmt.db_provisioner import drop_tenant_database
from app.modules.platform.tenant_mgmt.models import Tenant

from demo.attendance import create_demo_attendance
from demo.billing import create_demo_billing
from demo.features import create_demo_features
from demo.organisations import DEMO_ORGS, create_demo_org, create_demo_plans
from demo.schedule import create_demo_schedule
from demo.students import create_demo_students
from demo.users import create_demo_users


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


async def seed_all() -> None:
    """Create all demo data: plans → orgs → users → students → schedule → attendance → billing → features."""

    # Pre-check: if any demo org already exists, abort
    async with async_session_factory() as db:
        existing = await db.execute(
            select(Tenant).where(Tenant.slug.like("demo-%"))
        )
        if existing.scalars().first():
            _log("ERROR: Demo-organisaties bestaan al. Draai eerst --reset.")
            sys.exit(1)

    password = settings.demo_reset_password

    # 1. Plans (central DB)
    _log("=== Demo plans ===")
    async with async_session_factory() as db:
        plans = await create_demo_plans(db)
        await db.commit()

    # 2-8. Per org
    tenant_ids: dict[str, uuid.UUID] = {}
    first_owner_id: uuid.UUID | None = None

    for org_def in DEMO_ORGS:
        org_key = org_def["slug"].removeprefix("demo-")
        _log(f"\n=== {org_def['name']} ({org_key}) ===")

        # 2. Org + owner + provision + subscription (central DB)
        async with async_session_factory() as db:
            tenant, owner, groups = await create_demo_org(db, org_def, plans, password)
            tenant_id = tenant.id
            owner_id = owner.id
            tenant_ids[org_key] = tenant_id
            if first_owner_id is None:
                first_owner_id = owner_id

        # 3. Additional users (central DB)
        async with async_session_factory() as db:
            users = await create_demo_users(db, org_key, tenant_id, groups, password)
            # Include owner in the users dict for reference
            async with async_session_factory() as db2:
                owner_result = await db2.execute(select(User).where(User.id == owner_id))
                owner_user = owner_result.scalar_one()
            users["owner"] = owner_user

        # 4-7. Tenant-scoped data
        slug = org_def["slug"]
        await tenant_db_manager.get_engine(slug)
        factory = tenant_db_manager._session_factories[slug]

        async with factory() as tenant_db:
            # 4. Students + teacher assignments
            students = await create_demo_students(tenant_db, org_key, users, owner_id)

            # 5. Schedule (slots + instances)
            await create_demo_schedule(tenant_db, students, users)

            # 6. Attendance
            await create_demo_attendance(tenant_db, users)

            # 7. Billing (tuition plan + student billing + invoices)
            await create_demo_billing(tenant_db, slug, students, users)

            await tenant_db.commit()

    # 8. Feature trials & overrides (central DB)
    _log("\n=== Features ===")
    async with async_session_factory() as db:
        await create_demo_features(db, tenant_ids, first_owner_id)
        await db.commit()

    _log("\n=== Demo seed voltooid ===")
    _log(f"  Wachtwoord voor alle demo-accounts: {password}")
    _log("  Email-domein: @demo.yoohoo")
    for org_def in DEMO_ORGS:
        _log(f"  {org_def['name']}: {org_def['owner_email']}")


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------


async def teardown_all() -> None:
    """Remove all demo data: drop tenant DBs, delete tenants + users + plans."""
    _log("=== Demo teardown ===")

    async with async_session_factory() as db:
        # 1. Find demo tenants
        result = await db.execute(
            select(Tenant).where(Tenant.slug.like("demo-%"))
        )
        tenants = list(result.scalars().all())

        if not tenants:
            _log("  Geen demo-organisaties gevonden — niets te verwijderen")
        else:
            for tenant in tenants:
                slug = tenant.slug
                _log(f"  Verwijder org: {tenant.name} ({slug})")

                # Drop tenant database
                if tenant.is_provisioned:
                    try:
                        await drop_tenant_database(slug)
                        _log(f"    Database ps_t_{slug}_db verwijderd")
                    except Exception as e:
                        _log(f"    WARN: Database drop mislukt: {e}")

                # Remove cached engine
                await tenant_db_manager.remove_engine(slug)

                # Invalidate slug cache
                try:
                    from app.modules.products.school.path_dependency import invalidate_slug_to_id_cache
                    invalidate_slug_to_id_cache(slug)
                except Exception:
                    pass

                # Delete tenant (cascades memberships, groups, subscriptions, overrides, trials)
                await db.delete(tenant)

            await db.flush()

        # 2. Delete demo users
        user_result = await db.execute(
            select(User).where(User.email.like("%@demo.yoohoo"))
        )
        demo_users = list(user_result.scalars().all())
        for user in demo_users:
            await db.delete(user)
        if demo_users:
            _log(f"  {len(demo_users)} demo-gebruikers verwijderd")

        # 3. Delete demo plans
        plan_result = await db.execute(
            select(PlatformPlan).where(PlatformPlan.slug.like("demo-%"))
        )
        demo_plans = list(plan_result.scalars().all())
        for plan in demo_plans:
            await db.delete(plan)
        if demo_plans:
            _log(f"  {len(demo_plans)} demo-plannen verwijderd")

        await db.commit()

    _log("=== Teardown voltooid ===")
