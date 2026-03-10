"""Default permission groups for new tenants and platform-level groups."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import permission_registry
from app.modules.platform.auth.models import GroupPermission, PermissionGroup


DEFAULT_GROUPS = [
    {
        "slug": "beheerder",
        "name": "Beheerder",
        "description": "Volledige toegang tot alle organisatiefuncties",
        "permissions": None,  # None = ALL registered permissions
    },
    {
        "slug": "docent",
        "name": "Docent",
        "description": "Leerlingen, aanwezigheid en roosters beheren",
        "permissions": [
            "students.view_assigned",
            "students.create",
            "students.edit",
            "students.delete",
            "students.import",
            "students.assign",
            "attendance.view_assigned",
            "attendance.create",
            "attendance.edit",
            "attendance.delete",
            "schedule.view_assigned",
            "schedule.manage",
            "schedule.substitute",
            "notifications.view",
            "billing.view",
        ],
    },
    {
        "slug": "ouder",
        "name": "Ouder",
        "description": "Gegevens van eigen kinderen inzien",
        "permissions": [
            "students.view_own",
            "attendance.view_own",
            "schedule.view",
            "notifications.view",
            "billing.view_own",
        ],
    },
    {
        "slug": "medewerker",
        "name": "Medewerker",
        "description": "Externe medewerker - beperkte toegang tot toegewezen leerlingen",
        "permissions": [
            "students.view_assigned",
            "attendance.view_assigned",
            "attendance.create",
            "attendance.edit",
            "schedule.view_assigned",
            "schedule.manage",
            "notifications.view",
        ],
    },
]


async def create_default_groups(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict[str, PermissionGroup]:
    """Create default permission groups for a new tenant.

    Returns a dict of slug -> PermissionGroup.
    """
    all_codenames = permission_registry.get_all_codenames()
    created: dict[str, PermissionGroup] = {}

    for group_def in DEFAULT_GROUPS:
        group = PermissionGroup(
            tenant_id=tenant_id,
            name=group_def["name"],
            slug=group_def["slug"],
            description=group_def["description"],
            is_default=True,
        )
        db.add(group)
        await db.flush()

        # Determine which codenames to assign
        codenames = all_codenames if group_def["permissions"] is None else set(group_def["permissions"])
        for codename in codenames:
            gp = GroupPermission(group_id=group.id, permission_codename=codename)
            db.add(gp)

        created[group_def["slug"]] = group

    await db.flush()
    return created


DEFAULT_PLATFORM_GROUPS = [
    {
        "slug": "platform-admin",
        "name": "Platform Admin",
        "description": "Volledige toegang tot platformbeheer",
        "permissions": None,  # All platform.* permissions
    },
    {
        "slug": "support",
        "name": "Support",
        "description": "Gebruikers en audit logs bekijken, geen wijzigingen",
        "permissions": [
            "platform.view_stats",
            "platform.view_orgs",
            "platform.view_users",
            "platform.view_audit_logs",
        ],
    },
    {
        "slug": "nieuw",
        "name": "Nieuw",
        "description": "Landing-groep voor uitgenodigde platformgebruikers (geen rechten)",
        "permissions": [],  # Bewust leeg — NIET None (dat = alle rechten)
    },
]


async def create_default_platform_groups(
    db: AsyncSession,
) -> dict[str, PermissionGroup]:
    """Create default platform-level permission groups (tenant_id=None).

    Returns a dict of slug -> PermissionGroup. Skips groups that already exist.
    """
    all_platform_codenames = {
        c for c in permission_registry.get_all_codenames()
        if c.startswith("platform.")
    }
    created: dict[str, PermissionGroup] = {}

    for group_def in DEFAULT_PLATFORM_GROUPS:
        existing = await db.execute(
            select(PermissionGroup).where(
                PermissionGroup.tenant_id.is_(None),
                PermissionGroup.slug == group_def["slug"],
            )
        )
        if existing.scalar_one_or_none():
            continue

        group = PermissionGroup(
            tenant_id=None,
            name=group_def["name"],
            slug=group_def["slug"],
            description=group_def["description"],
            is_default=True,
        )
        db.add(group)
        await db.flush()

        codenames = all_platform_codenames if group_def["permissions"] is None else set(group_def["permissions"])
        for codename in codenames:
            gp = GroupPermission(group_id=group.id, permission_codename=codename)
            db.add(gp)

        created[group_def["slug"]] = group

    await db.flush()
    return created
