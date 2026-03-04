import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, send_email_safe
from app.core.exceptions import NotFoundError
from app.modules.tenant.notification.models import (
    InAppNotification,
    NotificationChannel,
    NotificationLog,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
)
from app.modules.tenant.notification.schemas import NotificationPreferenceUpdate

logger = structlog.get_logger()


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Preferences ───

    async def initialize_defaults(self) -> list[NotificationPreference]:
        """Create default preferences for all notification types."""
        created = []
        for ntype in NotificationType:
            result = await self.db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.notification_type == ntype
                )
            )
            if result.scalar_one_or_none():
                continue

            pref = NotificationPreference(
                notification_type=ntype,
                is_enabled=True,
                send_to_guardian=True,
                send_to_teacher=True,
                send_to_admin=False,
            )
            self.db.add(pref)
            created.append(pref)

        if created:
            await self.db.flush()
        return created

    async def get_preferences(self) -> list[NotificationPreference]:
        result = await self.db.execute(
            select(NotificationPreference).order_by(
                NotificationPreference.notification_type
            )
        )
        return list(result.scalars().all())

    async def get_preference(
        self, notification_type: NotificationType
    ) -> NotificationPreference:
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.notification_type == notification_type
            )
        )
        pref = result.scalar_one_or_none()
        if not pref:
            raise NotFoundError("NotificationPreference", notification_type.value)
        return pref

    async def update_preference(
        self,
        notification_type: NotificationType,
        data: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        pref = await self.get_preference(notification_type)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(pref, key, value)

        await self.db.flush()
        await self.db.refresh(pref)

        logger.info("notification.preference_updated", type=notification_type.value)
        return pref

    # ─── Send notification ───

    async def send_notification(
        self,
        notification_type: NotificationType,
        recipient_email: str,
        recipient_name: str | None,
        subject: str,
        html_body: str,
        context_data: dict | None = None,
    ) -> NotificationLog:
        """Create a log entry and send the email via circuit-breaker-protected sender."""
        log = NotificationLog(
            notification_type=notification_type,
            channel=NotificationChannel.email,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            status=NotificationStatus.pending,
            context_data=context_data,
        )
        self.db.add(log)
        await self.db.flush()

        success = await send_email_safe(recipient_email, subject, html_body, sender=EmailSender.NOTIFICATION)

        if success:
            log.status = NotificationStatus.sent
        else:
            log.status = NotificationStatus.failed
            log.error_message = "Email delivery failed or circuit breaker open"

        await self.db.flush()
        await self.db.refresh(log)

        logger.info(
            "notification.sent",
            type=notification_type.value,
            to=recipient_email,
            status=log.status.value,
        )
        return log

    # ─── In-App ───

    async def create_in_app(
        self,
        user_id: uuid.UUID,
        title: str,
        message: str,
        notification_type: NotificationType,
        context_data: dict | None = None,
    ) -> InAppNotification:
        notif = InAppNotification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            context_data=context_data,
        )
        self.db.add(notif)
        await self.db.flush()
        return notif

    async def list_in_app(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 25,
        unread_only: bool = False,
    ) -> tuple[list[InAppNotification], int]:
        query = select(InAppNotification).where(
            InAppNotification.user_id == user_id
        )

        if unread_only:
            query = query.where(InAppNotification.is_read.is_(False))

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(InAppNotification.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def mark_read(self, notif_id: uuid.UUID, user_id: uuid.UUID) -> InAppNotification:
        result = await self.db.execute(
            select(InAppNotification).where(
                InAppNotification.id == notif_id,
                InAppNotification.user_id == user_id,
            )
        )
        notif = result.scalar_one_or_none()
        if not notif:
            raise NotFoundError("InAppNotification", str(notif_id))

        notif.is_read = True
        await self.db.flush()
        await self.db.refresh(notif)
        return notif

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import update

        result = await self.db.execute(
            update(InAppNotification)
            .where(
                InAppNotification.user_id == user_id,
                InAppNotification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def get_unread_count(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                InAppNotification.user_id == user_id,
                InAppNotification.is_read.is_(False),
            )
        )
        return result.scalar() or 0

    # ─── Logs ───

    async def list_logs(
        self,
        page: int = 1,
        per_page: int = 25,
        notification_type: NotificationType | None = None,
        status: NotificationStatus | None = None,
    ) -> tuple[list[NotificationLog], int]:
        query = select(NotificationLog)

        if notification_type:
            query = query.where(NotificationLog.notification_type == notification_type)
        if status:
            query = query.where(NotificationLog.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(NotificationLog.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        return logs, total

    async def get_log(self, log_id: uuid.UUID) -> NotificationLog:
        result = await self.db.execute(
            select(NotificationLog).where(NotificationLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        if not log:
            raise NotFoundError("NotificationLog", str(log_id))
        return log
