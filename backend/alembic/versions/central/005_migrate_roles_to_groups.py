"""Migrate existing roles to permission groups (data migration)

Revision ID: 005_migrate_roles_to_groups
Revises: 004_add_permission_groups
Create Date: 2026-02-28

"""
import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "005_migrate_roles_to_groups"
down_revision: Union[str, None] = "004_add_permission_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default group definitions with their permissions
ROLE_TO_GROUP = {
    "school_admin": {
        "slug": "schoolbeheerder",
        "name": "Schoolbeheerder",
        "description": "Volledige toegang tot alle schoolfuncties",
        "permissions": [
            "students.view", "students.view_own", "students.create", "students.edit",
            "students.delete", "students.import", "students.manage_parents",
            "attendance.view", "attendance.view_own", "attendance.create",
            "attendance.edit", "attendance.delete",
            "schedule.view", "schedule.manage",
            "notifications.view", "notifications.manage",
            "invitations.view", "invitations.manage",
            "school_settings.view", "school_settings.edit",
        ],
    },
    "teacher": {
        "slug": "docent",
        "name": "Docent",
        "description": "Leerlingen, aanwezigheid en roosters beheren",
        "permissions": [
            "students.view", "students.create", "students.edit",
            "students.delete", "students.import",
            "attendance.view", "attendance.create", "attendance.edit", "attendance.delete",
            "schedule.view", "schedule.manage",
            "notifications.view",
        ],
    },
    "parent": {
        "slug": "ouder",
        "name": "Ouder",
        "description": "Gegevens van eigen kinderen inzien",
        "permissions": [
            "students.view_own",
            "attendance.view_own",
            "schedule.view",
            "notifications.view",
        ],
    },
}


def upgrade() -> None:
    conn = op.get_bind()

    # Get all tenants
    tenants = conn.execute(text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:
        # Create default groups for this tenant
        group_ids = {}
        for role_name, group_def in ROLE_TO_GROUP.items():
            group_id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO permission_groups (id, tenant_id, name, slug, description, is_default, created_at, updated_at) "
                    "VALUES (:id, :tenant_id, :name, :slug, :description, true, now(), now())"
                ),
                {
                    "id": group_id,
                    "tenant_id": tenant_id,
                    "name": group_def["name"],
                    "slug": group_def["slug"],
                    "description": group_def["description"],
                },
            )
            # Add permissions
            for codename in group_def["permissions"]:
                conn.execute(
                    text(
                        "INSERT INTO group_permissions (id, group_id, permission_codename) "
                        "VALUES (:id, :group_id, :codename)"
                    ),
                    {"id": uuid.uuid4(), "group_id": group_id, "codename": codename},
                )
            group_ids[role_name] = group_id

        # Migrate existing memberships to group assignments
        memberships = conn.execute(
            text(
                "SELECT user_id, role FROM tenant_memberships "
                "WHERE tenant_id = :tenant_id AND is_active = true AND role IS NOT NULL"
            ),
            {"tenant_id": tenant_id},
        ).fetchall()

        for user_id, role in memberships:
            group_id = group_ids.get(role)
            if group_id:
                # Check if assignment already exists
                existing = conn.execute(
                    text(
                        "SELECT id FROM user_group_assignments "
                        "WHERE user_id = :uid AND group_id = :gid"
                    ),
                    {"uid": user_id, "gid": group_id},
                ).fetchone()
                if not existing:
                    conn.execute(
                        text(
                            "INSERT INTO user_group_assignments (id, user_id, group_id, created_at, updated_at) "
                            "VALUES (:id, :uid, :gid, now(), now())"
                        ),
                        {"id": uuid.uuid4(), "uid": user_id, "gid": group_id},
                    )

        # Migrate existing invitations: map role -> group_id
        for role_name, group_id in group_ids.items():
            conn.execute(
                text(
                    "UPDATE invitations SET group_id = :gid "
                    "WHERE tenant_id = :tid AND role = :role AND group_id IS NULL"
                ),
                {"gid": group_id, "tid": tenant_id, "role": role_name},
            )


def downgrade() -> None:
    conn = op.get_bind()

    # Clear invitation group_id references
    conn.execute(text("UPDATE invitations SET group_id = NULL"))

    # Delete all user_group_assignments
    conn.execute(text("DELETE FROM user_group_assignments"))

    # Delete all group_permissions
    conn.execute(text("DELETE FROM group_permissions"))

    # Delete all permission_groups
    conn.execute(text("DELETE FROM permission_groups"))
