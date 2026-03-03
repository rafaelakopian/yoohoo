import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.event_bus import event_bus
from app.core.exceptions import ConflictError, NotFoundError, TenantDatabaseError
from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.models import TenantMembership, UserGroupAssignment
from app.modules.platform.auth.permissions_setup import create_default_groups
from app.db.tenant import tenant_db_manager
from app.modules.platform.tenant_mgmt.db_provisioner import create_tenant_database, drop_tenant_database
from app.modules.platform.tenant_mgmt.models import Tenant, TenantSettings
from app.modules.platform.tenant_mgmt.schemas import TenantCreate, TenantSettingsUpdate

logger = structlog.get_logger()


class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, data: TenantCreate, owner_id: uuid.UUID) -> Tenant:
        # Check slug uniqueness
        existing = await self.db.execute(
            select(Tenant).where(Tenant.slug == data.slug)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Tenant with slug '{data.slug}' already exists")

        tenant = Tenant(
            name=data.name,
            slug=data.slug,
            owner_id=owner_id,
        )
        self.db.add(tenant)
        await self.db.flush()

        # Create default settings
        tenant_settings = TenantSettings(tenant_id=tenant.id)
        self.db.add(tenant_settings)

        # Create owner membership
        membership = TenantMembership(
            user_id=owner_id,
            tenant_id=tenant.id,
            role=Role.SCHOOL_ADMIN,
        )
        self.db.add(membership)
        await self.db.flush()

        # Create default permission groups and assign owner to schoolbeheerder
        groups = await create_default_groups(self.db, tenant.id)
        admin_group = groups.get("schoolbeheerder")
        if admin_group:
            assignment = UserGroupAssignment(
                user_id=owner_id,
                group_id=admin_group.id,
            )
            self.db.add(assignment)
            await self.db.flush()

        logger.info("tenant.created", tenant_id=str(tenant.id), slug=tenant.slug)
        await event_bus.emit("tenant.created", tenant_id=tenant.id, slug=tenant.slug)

        return tenant

    async def provision_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = await self._get_tenant(tenant_id)

        if tenant.is_provisioned:
            raise ConflictError(f"Tenant '{tenant.slug}' is already provisioned")

        try:
            await create_tenant_database(tenant.slug)
        except Exception as e:
            logger.error("tenant.provision_failed", tenant_id=str(tenant_id), error=str(e))
            raise TenantDatabaseError(tenant.slug, str(e))

        tenant.is_provisioned = True
        await self.db.flush()

        logger.info("tenant.provisioned", tenant_id=str(tenant.id), slug=tenant.slug)
        await event_bus.emit("tenant.provisioned", tenant_id=tenant.id, slug=tenant.slug)

        return tenant

    async def delete_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = await self._get_tenant(tenant_id)
        tenant_id_str = str(tenant.id)
        tenant_slug = tenant.slug

        # Drop tenant database if provisioned
        if tenant.is_provisioned:
            await drop_tenant_database(tenant_slug)

        # Remove cached engine if it existed
        await tenant_db_manager.remove_engine(tenant_slug)

        # Invalidate slug-to-id cache
        from app.modules.tenant.path_dependency import invalidate_slug_to_id_cache
        invalidate_slug_to_id_cache(tenant_slug)

        # Hard delete tenant (cascades to settings + memberships via ON DELETE CASCADE)
        await self.db.delete(tenant)
        await self.db.flush()

        logger.info("tenant.deleted", tenant_id=tenant_id_str, slug=tenant_slug)
        await event_bus.emit("tenant.deleted", tenant_id=tenant_id, slug=tenant_slug)

        return tenant

    async def list_tenants(self, user_id: uuid.UUID | None = None) -> list[Tenant]:
        query = select(Tenant).where(Tenant.is_active)
        if user_id:
            query = (
                query.join(TenantMembership)
                .where(TenantMembership.user_id == user_id)
                .where(TenantMembership.is_active)
            )
        result = await self.db.execute(query.order_by(Tenant.name))
        return list(result.scalars().all())

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        return await self._get_tenant(tenant_id)

    async def get_settings(self, tenant_id: uuid.UUID) -> TenantSettings:
        result = await self.db.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            raise NotFoundError("TenantSettings", str(tenant_id))
        return settings

    async def update_settings(
        self, tenant_id: uuid.UUID, data: TenantSettingsUpdate
    ) -> TenantSettings:
        settings = await self.get_settings(tenant_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(settings, key, value)

        await self.db.flush()
        return settings

    async def _get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        result = await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.settings))
            .where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundError("Tenant", str(tenant_id))
        return tenant
