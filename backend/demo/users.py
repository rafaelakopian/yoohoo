"""Demo user definitions and creation logic."""

import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.platform.auth.models import (
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# User definitions per org (keyed by org slug suffix)
# ---------------------------------------------------------------------------

DEMO_USERS: dict[str, list[dict]] = {
    "klankvlek": [
        {"email": "klankvlek-docent1@demo.yoohoo", "name": "Pieter van Dijk", "group": "docent"},
        {"email": "klankvlek-docent2@demo.yoohoo", "name": "Anne Smit", "group": "docent"},
        {"email": "klankvlek-ouder1@demo.yoohoo", "name": "Sandra de Jong", "group": "ouder"},
        {"email": "klankvlek-ouder2@demo.yoohoo", "name": "Robert Bakker", "group": "ouder"},
    ],
    "hartman": [
        {"email": "hartman-docent1@demo.yoohoo", "name": "Thomas Willems", "group": "docent"},
        {"email": "hartman-docent2@demo.yoohoo", "name": "Eva Hendriks", "group": "docent"},
        {"email": "hartman-ouder1@demo.yoohoo", "name": "Michel Bos", "group": "ouder"},
        {"email": "hartman-ouder2@demo.yoohoo", "name": "Ingrid Scholten", "group": "ouder"},
    ],
    "vos": [
        {"email": "vos-docent1@demo.yoohoo", "name": "Karel Vermeer", "group": "docent"},
        {"email": "vos-docent2@demo.yoohoo", "name": "Floor Maas", "group": "docent"},
        {"email": "vos-ouder1@demo.yoohoo", "name": "Henk de Graaf", "group": "ouder"},
        {"email": "vos-ouder2@demo.yoohoo", "name": "Marion Kok", "group": "ouder"},
    ],
}


async def create_demo_users(
    db: AsyncSession,
    org_key: str,
    tenant_id,
    groups: dict[str, PermissionGroup],
    password: str,
) -> dict[str, User]:
    """Create demo users for one org. Returns dict keyed by role+index: docent1, docent2, ouder1, ouder2."""
    user_defs = DEMO_USERS[org_key]
    created: dict[str, User] = {}
    docent_idx = 0
    ouder_idx = 0

    for user_def in user_defs:
        user = User(
            email=user_def["email"],
            hashed_password=hash_password(password),
            full_name=user_def["name"],
            is_active=True,
            is_superadmin=False,
            email_verified=True,
        )
        db.add(user)
        await db.flush()

        # Membership
        db.add(TenantMembership(
            user_id=user.id, tenant_id=tenant_id, is_active=True, membership_type="full",
        ))

        # Group assignment
        group_slug = user_def["group"]
        if group_slug in groups:
            db.add(UserGroupAssignment(user_id=user.id, group_id=groups[group_slug].id))

        await db.flush()

        if group_slug == "docent":
            docent_idx += 1
            created[f"docent{docent_idx}"] = user
        else:
            ouder_idx += 1
            created[f"ouder{ouder_idx}"] = user

    await db.commit()
    _log(f"    {len(user_defs)} gebruikers aangemaakt")
    return created
