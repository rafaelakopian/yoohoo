from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_types import all_types
from app.db.central import get_central_db
from app.dependencies import get_arq
from app.modules.platform.auth.dependencies import get_current_user, require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.notifications.schemas import (
    CreatePlatformNotification,
    InboxItem,
    NotificationTypeInfo,
    PaginatedInbox,
    PaginatedNotifications,
    PlatformNotificationListItem,
    PlatformNotificationResponse,
    PreferenceResponse,
    UpdatePlatformNotification,
    UpdatePreference,
)
from app.modules.platform.notifications.service import PlatformNotificationService

# ---------------------------------------------------------------------------
# Admin router — create, list, publish, delete notifications
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/platform/notifications", tags=["platform-notifications"])


def _get_service(db: AsyncSession = Depends(get_central_db)) -> PlatformNotificationService:
    return PlatformNotificationService(db)


@admin_router.get("/types", response_model=list[NotificationTypeInfo])
async def list_notification_types(
    _: User = Depends(require_permission("platform_notifications.manage")),
):
    """List all registered platform notification types."""
    return [
        NotificationTypeInfo(
            code=t.code, label=t.label, description=t.description, default_severity=t.default_severity,
        )
        for t in all_types()
    ]


@admin_router.post("", response_model=PlatformNotificationResponse, status_code=201)
async def create_notification(
    data: CreatePlatformNotification,
    current_user: User = Depends(require_permission("platform_notifications.manage")),
    service: PlatformNotificationService = Depends(_get_service),
    db: AsyncSession = Depends(get_central_db),
):
    notification = await service.create_notification(data.model_dump(), current_user.id)
    await db.commit()
    return PlatformNotificationResponse(
        **{c.key: getattr(notification, c.key) for c in notification.__table__.columns},
        recipient_count=0,
    )


@admin_router.get("", response_model=PaginatedNotifications)
async def list_notifications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("platform_notifications.manage")),
    service: PlatformNotificationService = Depends(_get_service),
):
    items, total = await service.list_notifications(skip=skip, limit=limit)
    return PaginatedNotifications(
        items=[
            PlatformNotificationListItem(
                **{c.key: getattr(n, c.key) for c in n.__table__.columns},
                recipient_count=len(n.recipients) if hasattr(n, "recipients") and n.recipients else 0,
            )
            for n in items
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@admin_router.get("/{notification_id}", response_model=PlatformNotificationResponse)
async def get_notification(
    notification_id: str,
    _: User = Depends(require_permission("platform_notifications.manage")),
    service: PlatformNotificationService = Depends(_get_service),
):
    import uuid as uuid_mod
    notification = await service.get_notification(uuid_mod.UUID(notification_id))
    return PlatformNotificationResponse(
        **{c.key: getattr(notification, c.key) for c in notification.__table__.columns},
        recipient_count=len(notification.recipients),
    )


@admin_router.put("/{notification_id}", response_model=PlatformNotificationResponse)
async def update_notification(
    notification_id: str,
    data: UpdatePlatformNotification,
    _: User = Depends(require_permission("platform_notifications.manage")),
    service: PlatformNotificationService = Depends(_get_service),
    db: AsyncSession = Depends(get_central_db),
):
    import uuid as uuid_mod
    notification = await service.update_notification(
        uuid_mod.UUID(notification_id),
        data.model_dump(exclude_unset=True),
    )
    await db.commit()
    return PlatformNotificationResponse(
        **{c.key: getattr(notification, c.key) for c in notification.__table__.columns},
        recipient_count=len(notification.recipients),
    )


@admin_router.put("/{notification_id}/publish")
async def publish_notification(
    notification_id: str,
    _: User = Depends(require_permission("platform_notifications.manage")),
    service: PlatformNotificationService = Depends(_get_service),
    db: AsyncSession = Depends(get_central_db),
    arq_pool=Depends(get_arq),
):
    import uuid as uuid_mod
    count = await service.publish_notification(
        uuid_mod.UUID(notification_id), arq_pool=arq_pool,
    )
    await db.commit()
    return {"message": f"Melding gepubliceerd naar {count} ontvangers"}


@admin_router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: str,
    _: User = Depends(require_permission("platform_notifications.manage")),
    service: PlatformNotificationService = Depends(_get_service),
    db: AsyncSession = Depends(get_central_db),
):
    import uuid as uuid_mod
    await service.delete_notification(uuid_mod.UUID(notification_id))
    await db.commit()


# ---------------------------------------------------------------------------
# User router — inbox for authenticated users
# ---------------------------------------------------------------------------

user_router = APIRouter(prefix="/platform/notifications", tags=["platform-notifications"])


@user_router.get("/inbox", response_model=PaginatedInbox)
async def get_inbox(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: PlatformNotificationService = Depends(_get_service),
):
    items, total, unread_count = await service.get_inbox(
        current_user.id, skip=skip, limit=limit,
    )
    return PaginatedInbox(
        items=[InboxItem(**item) for item in items],
        total=total,
        unread_count=unread_count,
    )


@user_router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    service: PlatformNotificationService = Depends(_get_service),
):
    count = await service.get_unread_count(current_user.id)
    return {"count": count}


@user_router.put("/{recipient_id}/read")
async def mark_read(
    recipient_id: str,
    current_user: User = Depends(get_current_user),
    service: PlatformNotificationService = Depends(_get_service),
    db: AsyncSession = Depends(get_central_db),
):
    import uuid as uuid_mod
    await service.mark_read(uuid_mod.UUID(recipient_id), current_user.id)
    await db.commit()
    return {"message": "Gelezen"}


@user_router.put("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    service: PlatformNotificationService = Depends(_get_service),
    db: AsyncSession = Depends(get_central_db),
):
    count = await service.mark_all_read(current_user.id)
    await db.commit()
    return {"message": f"{count} meldingen als gelezen gemarkeerd"}


# ---------------------------------------------------------------------------
# Tenant preferences router — mounted under /orgs/{slug}
# ---------------------------------------------------------------------------

tenant_router = APIRouter(
    prefix="/notifications/platform-preferences",
    tags=["platform-notifications"],
)


@tenant_router.get("", response_model=list[PreferenceResponse])
async def get_preferences(
    request: Request,
    _: User = Depends(require_permission("platform_notifications.manage_preferences")),
    service: PlatformNotificationService = Depends(_get_service),
):
    tenant_id = request.state.tenant_id
    prefs = await service.get_preferences(tenant_id)
    return [PreferenceResponse(**p) for p in prefs]


@tenant_router.put("/{notification_type}", response_model=PreferenceResponse)
async def update_preference(
    notification_type: str,
    data: UpdatePreference,
    request: Request,
    _: User = Depends(require_permission("platform_notifications.manage_preferences")),
    service: PlatformNotificationService = Depends(_get_service),
    db: AsyncSession = Depends(get_central_db),
):
    from app.core.notification_types import get_type

    tenant_id = request.state.tenant_id
    pref = await service.update_preference(
        tenant_id, notification_type, data.model_dump(exclude_unset=True),
    )
    await db.commit()

    type_def = get_type(notification_type)
    return PreferenceResponse(
        id=pref.id,
        notification_type=pref.notification_type,
        type_label=type_def.label if type_def else notification_type,
        type_description=type_def.description if type_def else "",
        is_enabled=pref.is_enabled,
        email_enabled=pref.email_enabled,
        extra_recipient_group_ids=pref.extra_recipient_group_ids,
    )
