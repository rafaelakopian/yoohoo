import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.db.base import CentralBase, TenantBase

# Import models so they're registered with metadata
from app.modules.platform.auth.models import (  # noqa: F401
    User, TenantMembership, RefreshToken, Invitation, PasswordResetToken, AuditLog,
    PermissionGroup, GroupPermission, UserGroupAssignment,
)
from app.modules.platform.tenant_mgmt.models import Tenant, TenantSettings  # noqa: F401
from app.modules.products.school.student.models import Student, ParentStudentLink  # noqa: F401
from app.modules.products.school.attendance.models import AttendanceRecord  # noqa: F401
from app.modules.products.school.schedule.models import LessonSlot, LessonInstance, Holiday  # noqa: F401
from app.modules.products.school.notification.models import NotificationPreference, NotificationLog, InAppNotification  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Determine which mode we're running in
# Usage: alembic -x mode=central upgrade central@head
# Usage: alembic -x mode=tenant -x tenant_slug=myschool upgrade tenant@head
mode = context.get_x_argument(as_dictionary=True).get("mode", "central")


if mode == "central":
    target_metadata = CentralBase.metadata
    url = settings.central_database_url_sync
elif mode == "tenant":
    target_metadata = TenantBase.metadata
    tenant_slug = context.get_x_argument(as_dictionary=True).get("tenant_slug")
    if not tenant_slug:
        raise ValueError("tenant_slug is required for tenant migrations")
    url = settings.tenant_database_url_sync(tenant_slug)
else:
    raise ValueError(f"Unknown migration mode: {mode}")


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
