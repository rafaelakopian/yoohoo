"""Rename school_* columns and permission codenames to org_*.

Revision ID: 013
Revises: 012
Create Date: 2026-03-04
"""

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Column renames in tenant_settings ---
    op.alter_column("tenant_settings", "school_name", new_column_name="org_name")
    op.alter_column("tenant_settings", "school_address", new_column_name="org_address")
    op.alter_column("tenant_settings", "school_phone", new_column_name="org_phone")
    op.alter_column("tenant_settings", "school_email", new_column_name="org_email")

    # --- Permission codename renames ---
    op.execute(
        "UPDATE group_permissions "
        "SET permission_codename = 'org_settings.view' "
        "WHERE permission_codename = 'school_settings.view'"
    )
    op.execute(
        "UPDATE group_permissions "
        "SET permission_codename = 'org_settings.edit' "
        "WHERE permission_codename = 'school_settings.edit'"
    )

    # --- Default group rename ---
    op.execute(
        "UPDATE permission_groups "
        "SET slug = 'beheerder', name = 'Beheerder', "
        "description = 'Volledige toegang tot alle organisatiefuncties' "
        "WHERE slug = 'schoolbeheerder'"
    )


def downgrade() -> None:
    op.alter_column("tenant_settings", "org_name", new_column_name="school_name")
    op.alter_column("tenant_settings", "org_address", new_column_name="school_address")
    op.alter_column("tenant_settings", "org_phone", new_column_name="school_phone")
    op.alter_column("tenant_settings", "org_email", new_column_name="school_email")

    op.execute(
        "UPDATE group_permissions "
        "SET permission_codename = 'school_settings.view' "
        "WHERE permission_codename = 'org_settings.view'"
    )
    op.execute(
        "UPDATE group_permissions "
        "SET permission_codename = 'school_settings.edit' "
        "WHERE permission_codename = 'org_settings.edit'"
    )
    op.execute(
        "UPDATE permission_groups "
        "SET slug = 'schoolbeheerder', name = 'Schoolbeheerder', "
        "description = 'Volledige toegang tot alle schoolfuncties' "
        "WHERE slug = 'beheerder'"
    )
