"""Database seed script for initial Yoohoo setup.

Creates superadmin user, first tenant, provisions tenant database,
creates default permission groups, and assigns admin to beheerder.

Usage:
    docker compose exec -T api python scripts/seed.py

Environment variables:
    SEED_ADMIN_EMAIL     — Admin email (required)
    SEED_ADMIN_PASSWORD  — Admin password (required)
    SEED_ADMIN_NAME      — Admin full name (default: Admin Yoohoo)
    SEED_TENANT_NAME     — Tenant display name (default: Pianoschool Apeldoorn)
    SEED_TENANT_SLUG     — Tenant slug (default: pianoschool-apeldoorn)

Output:
    Status messages to stderr only. Credentials to SEED_OUTPUT_FILE if set.
"""

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def log(msg: str) -> None:
    """Print to stderr only — never stdout (prevents credential leakage in CI)."""
    print(msg, file=sys.stderr)


async def seed() -> None:
    from app.core.security import hash_password
    from app.db.central import async_session_factory
    from app.modules.platform.auth.models import (
        TenantMembership,
        User,
        UserGroupAssignment,
    )
    from app.modules.platform.auth.permissions_setup import create_default_groups
    from app.modules.platform.tenant_mgmt.db_provisioner import (
        create_tenant_database,
    )
    from app.modules.platform.tenant_mgmt.models import Tenant, TenantSettings

    # Read config from environment
    admin_email = os.environ.get("SEED_ADMIN_EMAIL")
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
    admin_name = os.environ.get("SEED_ADMIN_NAME", "Admin Yoohoo")
    tenant_name = os.environ.get("SEED_TENANT_NAME", "Pianoschool Apeldoorn")
    tenant_slug = os.environ.get("SEED_TENANT_SLUG", "pianoschool-apeldoorn")
    output_file = os.environ.get("SEED_OUTPUT_FILE")

    if not admin_email or not admin_password:
        log("ERROR: SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD are required")
        sys.exit(1)

    async with async_session_factory() as db:
        db: AsyncSession

        # --- 1. Create superadmin user (idempotent) ---
        existing_user = await db.execute(
            select(User).where(User.email == admin_email)
        )
        user = existing_user.scalar_one_or_none()

        if user:
            log(f"Admin user '{admin_email}' already exists — skipping")
        else:
            user = User(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                full_name=admin_name,
                is_active=True,
                is_superadmin=True,
                email_verified=True,
            )
            db.add(user)
            await db.flush()
            log(f"Created superadmin: {admin_email}")

        # --- 2. Create tenant (idempotent) ---
        existing_tenant = await db.execute(
            select(Tenant).where(Tenant.slug == tenant_slug)
        )
        tenant = existing_tenant.scalar_one_or_none()

        if tenant:
            log(f"Tenant '{tenant_slug}' already exists — skipping")
        else:
            tenant = Tenant(
                name=tenant_name,
                slug=tenant_slug,
                owner_id=user.id,
                is_active=True,
                is_provisioned=False,
            )
            db.add(tenant)
            await db.flush()

            # Tenant settings
            settings_obj = TenantSettings(
                tenant_id=tenant.id,
                org_name=tenant_name,
            )
            db.add(settings_obj)
            await db.flush()
            log(f"Created tenant: {tenant_name} ({tenant_slug})")

        # --- 3. Create membership (idempotent) ---
        existing_membership = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == tenant.id,
            )
        )
        if not existing_membership.scalar_one_or_none():
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                is_active=True,
                membership_type="full",
            )
            db.add(membership)
            await db.flush()
            log("Created tenant membership")

        await db.commit()

    # --- 4. Provision tenant database (idempotent) ---
    if not tenant.is_provisioned:
        log(f"Provisioning tenant database for '{tenant_slug}'...")
        await create_tenant_database(tenant_slug)

        async with async_session_factory() as db:
            t = await db.execute(
                select(Tenant).where(Tenant.slug == tenant_slug)
            )
            t_obj = t.scalar_one()
            t_obj.is_provisioned = True
            await db.commit()
        log("Tenant database provisioned")
    else:
        log("Tenant database already provisioned — skipping")

    # --- 5. Create default permission groups (idempotent) ---
    async with async_session_factory() as db:
        from app.modules.platform.auth.models import PermissionGroup

        existing_groups = await db.execute(
            select(PermissionGroup).where(
                PermissionGroup.tenant_id == tenant.id
            )
        )
        if not existing_groups.scalars().first():
            groups = await create_default_groups(db, tenant.id)
            log(f"Created {len(groups)} default permission groups")

            # Assign admin to beheerder
            if "beheerder" in groups:
                assignment = UserGroupAssignment(
                    user_id=user.id,
                    group_id=groups["beheerder"].id,
                )
                db.add(assignment)
                log("Assigned admin to 'beheerder' group")

            await db.commit()
        else:
            log("Permission groups already exist — skipping")

    # --- 6. Output credentials ---
    log("")
    log("=== Seed completed successfully ===")
    log(f"  Admin: {admin_email}")
    log(f"  Tenant: {tenant_name} ({tenant_slug})")

    if output_file:
        with open(output_file, "w") as f:
            f.write(f"admin_email={admin_email}\n")
            f.write(f"admin_password={admin_password}\n")
            f.write(f"tenant_slug={tenant_slug}\n")
        os.chmod(output_file, 0o600)
        log(f"  Credentials written to: {output_file}")


if __name__ == "__main__":
    asyncio.run(seed())
