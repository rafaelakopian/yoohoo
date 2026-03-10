import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.notification_types import PLATFORM_NOTIFICATION_TYPES, get_type
from app.modules.platform.auth.models import (
    PermissionGroup,
    User,
    UserGroupAssignment,
)
from app.modules.platform.notifications.models import (
    PlatformNotification,
    PlatformNotificationPreference,
    PlatformNotificationRecipient,
)
from app.modules.platform.tenant_mgmt.models import Tenant

logger = structlog.get_logger()


class PlatformNotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Admin: CRUD
    # ------------------------------------------------------------------

    async def create_notification(
        self, data: dict, created_by_id: uuid.UUID,
    ) -> PlatformNotification:
        """Create a draft platform notification."""
        notif_type = data.get("notification_type", "")
        if notif_type not in PLATFORM_NOTIFICATION_TYPES:
            raise NotFoundError(f"Onbekend notificatietype: {notif_type}")

        notification = PlatformNotification(
            notification_type=notif_type,
            title=data["title"],
            message=data["message"],
            severity=data.get("severity", get_type(notif_type).default_severity),
            created_by_id=created_by_id,
            target_scope=data.get("target_scope", "all"),
            target_tenant_ids=data.get("target_tenant_ids"),
            extra_data=data.get("extra_data"),
        )
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def get_notification(self, notification_id: uuid.UUID) -> PlatformNotification:
        result = await self.db.execute(
            select(PlatformNotification)
            .options(selectinload(PlatformNotification.recipients))
            .where(PlatformNotification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if not notification:
            raise NotFoundError("Melding niet gevonden")
        return notification

    async def list_notifications(
        self, skip: int = 0, limit: int = 20,
    ) -> tuple[list[PlatformNotification], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(PlatformNotification)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(PlatformNotification)
            .options(selectinload(PlatformNotification.recipients))
            .order_by(PlatformNotification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(result.scalars().all())
        return items, total

    async def update_notification(
        self, notification_id: uuid.UUID, data: dict,
    ) -> PlatformNotification:
        notification = await self.get_notification(notification_id)
        if notification.is_published:
            raise ConflictError("Gepubliceerde meldingen kunnen niet worden bewerkt")

        for key, value in data.items():
            if value is not None and hasattr(notification, key):
                setattr(notification, key, value)

        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def delete_notification(self, notification_id: uuid.UUID) -> None:
        notification = await self.get_notification(notification_id)
        if notification.is_published:
            raise ConflictError("Gepubliceerde meldingen kunnen niet worden verwijderd")
        await self.db.delete(notification)
        await self.db.flush()

    # ------------------------------------------------------------------
    # Admin: Publish (fan-out)
    # ------------------------------------------------------------------

    async def publish_notification(
        self, notification_id: uuid.UUID, *, arq_pool=None,
    ) -> int:
        """Publish a notification: fan-out to all eligible recipients."""
        notification = await self.get_notification(notification_id)
        if notification.is_published:
            raise ConflictError("Melding is al gepubliceerd")

        # Determine target tenants
        tenants = await self._get_target_tenants(notification)

        # Collect unique recipients per tenant
        all_recipients: dict[uuid.UUID, uuid.UUID | None] = {}  # user_id -> tenant_id

        for tenant in tenants:
            # Check tenant preferences
            pref = await self._get_preference(tenant.id, notification.notification_type)
            if pref and not pref.is_enabled:
                continue

            # Get recipients for this tenant
            user_ids = await self._get_tenant_recipients(
                tenant.id,
                extra_group_ids=pref.extra_recipient_group_ids if pref else None,
            )
            for uid in user_ids:
                if uid not in all_recipients:
                    all_recipients[uid] = tenant.id

        # Create recipient records
        for user_id, tenant_id in all_recipients.items():
            recipient = PlatformNotificationRecipient(
                notification_id=notification.id,
                user_id=user_id,
                tenant_id=tenant_id,
            )
            self.db.add(recipient)

        # Mark as published
        notification.is_published = True
        notification.published_at = datetime.now(timezone.utc)

        await self.db.flush()

        # Send emails (background)
        if arq_pool:
            for user_id, tenant_id in all_recipients.items():
                pref = await self._get_preference(tenant_id, notification.notification_type) if tenant_id else None
                if pref is None or pref.email_enabled:
                    await self._enqueue_email(arq_pool, notification, user_id)

        logger.info(
            "platform_notification.published",
            notification_id=str(notification.id),
            recipient_count=len(all_recipients),
        )

        return len(all_recipients)

    async def _get_target_tenants(self, notification: PlatformNotification) -> list[Tenant]:
        """Get the list of target tenants for a notification."""
        query = select(Tenant).where(Tenant.is_active.is_(True))

        if notification.target_scope == "specific" and notification.target_tenant_ids:
            query = query.where(Tenant.id.in_(notification.target_tenant_ids))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_tenant_recipients(
        self, tenant_id: uuid.UUID, *, extra_group_ids: list | None = None,
    ) -> list[uuid.UUID]:
        """Get recipient user IDs for a tenant: owner + admin groups + extra groups."""
        user_ids: set[uuid.UUID] = set()

        # 1. Tenant owner (stored on Tenant.owner_id)
        tenant_result = await self.db.execute(
            select(Tenant.owner_id).where(Tenant.id == tenant_id)
        )
        owner_id = tenant_result.scalar_one_or_none()
        if owner_id:
            user_ids.add(owner_id)

        # 2. Users in "beheerder" group for this tenant
        admin_group_result = await self.db.execute(
            select(PermissionGroup.id).where(
                PermissionGroup.tenant_id == tenant_id,
                PermissionGroup.slug == "beheerder",
            )
        )
        admin_group_id = admin_group_result.scalar_one_or_none()
        if admin_group_id:
            admin_users_result = await self.db.execute(
                select(UserGroupAssignment.user_id).where(
                    UserGroupAssignment.group_id == admin_group_id,
                )
            )
            for row in admin_users_result:
                user_ids.add(row[0])

        # 3. Extra configured groups
        if extra_group_ids:
            extra_users_result = await self.db.execute(
                select(UserGroupAssignment.user_id).where(
                    UserGroupAssignment.group_id.in_(extra_group_ids),
                )
            )
            for row in extra_users_result:
                user_ids.add(row[0])

        return list(user_ids)

    async def _get_preference(
        self, tenant_id: uuid.UUID | None, notification_type: str,
    ) -> PlatformNotificationPreference | None:
        if tenant_id is None:
            return None
        result = await self.db.execute(
            select(PlatformNotificationPreference).where(
                PlatformNotificationPreference.tenant_id == tenant_id,
                PlatformNotificationPreference.notification_type == notification_type,
            )
        )
        return result.scalar_one_or_none()

    async def _enqueue_email(
        self, arq_pool, notification: PlatformNotification, user_id: uuid.UUID,
    ) -> None:
        """Enqueue an email notification for a user."""
        user_result = await self.db.execute(
            select(User.email, User.full_name).where(User.id == user_id)
        )
        row = user_result.one_or_none()
        if not row:
            return

        from app.core.email import build_platform_notification_email
        subject, html_body = build_platform_notification_email(
            title=notification.title,
            message=notification.message,
            severity=notification.severity,
        )

        try:
            await arq_pool.enqueue_job(
                "send_email_job",
                to=row.email,
                subject=subject,
                html_body=html_body,
            )
        except Exception:
            logger.warning(
                "platform_notification.email_enqueue_failed",
                user_id=str(user_id),
                notification_id=str(notification.id),
            )

    # ------------------------------------------------------------------
    # System: automated notifications (cron jobs, feature lifecycle)
    # ------------------------------------------------------------------

    async def send_system(
        self,
        *,
        tenant_id: uuid.UUID,
        notification_type: str,
        title: str,
        message: str,
        extra_data: dict | None = None,
        arq_pool=None,
    ) -> PlatformNotification:
        """Create and immediately publish a system-generated notification.

        Used by cron jobs and feature lifecycle events. No human author
        (created_by_id=None), auto-published, targeted at a single tenant.
        """
        if notification_type not in PLATFORM_NOTIFICATION_TYPES:
            raise NotFoundError(f"Onbekend notificatietype: {notification_type}")

        now = datetime.now(timezone.utc)
        notification = PlatformNotification(
            notification_type=notification_type,
            title=title,
            message=message,
            severity=get_type(notification_type).default_severity,
            created_by_id=None,
            is_published=True,
            published_at=now,
            target_scope="specific",
            target_tenant_ids=[str(tenant_id)],
            extra_data=extra_data,
        )
        self.db.add(notification)
        await self.db.flush()

        # Fan-out to tenant recipients (owner + admin groups)
        pref = await self._get_preference(tenant_id, notification_type)
        if pref and not pref.is_enabled:
            logger.info(
                "platform_notification.send_system.disabled_by_preference",
                tenant_id=str(tenant_id),
                notification_type=notification_type,
            )
            return notification

        user_ids = await self._get_tenant_recipients(
            tenant_id,
            extra_group_ids=pref.extra_recipient_group_ids if pref else None,
        )

        for uid in user_ids:
            recipient = PlatformNotificationRecipient(
                notification_id=notification.id,
                user_id=uid,
                tenant_id=tenant_id,
            )
            self.db.add(recipient)

        await self.db.flush()

        # Enqueue emails via arq
        if arq_pool:
            for uid in user_ids:
                if pref is None or pref.email_enabled:
                    await self._enqueue_email(arq_pool, notification, uid)

        logger.info(
            "platform_notification.send_system",
            notification_type=notification_type,
            tenant_id=str(tenant_id),
            recipient_count=len(user_ids),
        )

        return notification

    # ------------------------------------------------------------------
    # User inbox
    # ------------------------------------------------------------------

    async def get_inbox(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 20,
    ) -> tuple[list[dict], int, int]:
        """Get a user's platform notification inbox. Returns (items, total, unread_count)."""
        base = select(PlatformNotificationRecipient).where(
            PlatformNotificationRecipient.user_id == user_id,
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        unread_result = await self.db.execute(
            select(func.count()).select_from(
                base.where(PlatformNotificationRecipient.is_read.is_(False)).subquery()
            )
        )
        unread_count = unread_result.scalar() or 0

        result = await self.db.execute(
            select(PlatformNotificationRecipient)
            .options(selectinload(PlatformNotificationRecipient.notification))
            .where(PlatformNotificationRecipient.user_id == user_id)
            .order_by(PlatformNotificationRecipient.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        recipients = list(result.scalars().all())

        items = []
        for r in recipients:
            n = r.notification
            items.append({
                "id": r.id,
                "notification_id": n.id,
                "notification_type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "severity": n.severity,
                "is_read": r.is_read,
                "read_at": r.read_at,
                "created_at": n.published_at or n.created_at,
            })

        return items, total, unread_count

    async def get_unread_count(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(PlatformNotificationRecipient).where(
                PlatformNotificationRecipient.user_id == user_id,
                PlatformNotificationRecipient.is_read.is_(False),
            )
        )
        return result.scalar() or 0

    async def mark_read(self, recipient_id: uuid.UUID, user_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(PlatformNotificationRecipient).where(
                PlatformNotificationRecipient.id == recipient_id,
                PlatformNotificationRecipient.user_id == user_id,
            )
        )
        recipient = result.scalar_one_or_none()
        if not recipient:
            raise NotFoundError("Melding niet gevonden")

        if not recipient.is_read:
            recipient.is_read = True
            recipient.read_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            update(PlatformNotificationRecipient)
            .where(
                PlatformNotificationRecipient.user_id == user_id,
                PlatformNotificationRecipient.is_read.is_(False),
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.db.flush()
        return result.rowcount

    # ------------------------------------------------------------------
    # Tenant preferences
    # ------------------------------------------------------------------

    async def get_preferences(self, tenant_id: uuid.UUID) -> list[dict]:
        """Get all notification preferences for a tenant (fills defaults for missing types)."""
        result = await self.db.execute(
            select(PlatformNotificationPreference).where(
                PlatformNotificationPreference.tenant_id == tenant_id,
            )
        )
        existing = {p.notification_type: p for p in result.scalars().all()}

        preferences = []
        for code, type_def in PLATFORM_NOTIFICATION_TYPES.items():
            pref = existing.get(code)
            preferences.append({
                "id": pref.id if pref else None,
                "notification_type": code,
                "type_label": type_def.label,
                "type_description": type_def.description,
                "is_enabled": pref.is_enabled if pref else True,
                "email_enabled": pref.email_enabled if pref else True,
                "extra_recipient_group_ids": pref.extra_recipient_group_ids if pref else None,
            })

        return preferences

    async def update_preference(
        self, tenant_id: uuid.UUID, notification_type: str, data: dict,
    ) -> PlatformNotificationPreference:
        """Update (or create) a preference for a tenant + notification type."""
        if notification_type not in PLATFORM_NOTIFICATION_TYPES:
            raise NotFoundError(f"Onbekend notificatietype: {notification_type}")

        result = await self.db.execute(
            select(PlatformNotificationPreference).where(
                PlatformNotificationPreference.tenant_id == tenant_id,
                PlatformNotificationPreference.notification_type == notification_type,
            )
        )
        pref = result.scalar_one_or_none()

        if pref is None:
            pref = PlatformNotificationPreference(
                tenant_id=tenant_id,
                notification_type=notification_type,
            )
            self.db.add(pref)

        for key, value in data.items():
            if value is not None and hasattr(pref, key):
                setattr(pref, key, value)

        await self.db.flush()
        await self.db.refresh(pref)
        return pref
