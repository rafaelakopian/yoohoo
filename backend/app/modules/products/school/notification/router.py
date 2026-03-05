import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_tenant_db
from app.modules.platform.auth.dependencies import (
    DataScope,
    get_data_scope,
    require_any_permission,
    require_permission,
)
from app.modules.platform.auth.models import User
from app.modules.products.school.notification.models import NotificationStatus, NotificationType
from app.modules.products.school.notification.schemas import (
    InAppNotificationListResponse,
    InAppNotificationResponse,
    InAppUnreadCount,
    NotificationLogListResponse,
    NotificationLogResponse,
    NotificationPreferenceListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)
from app.modules.products.school.notification.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def get_notification_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> NotificationService:
    return NotificationService(db)


# ─── Preferences ───


@router.get("/preferences/", response_model=NotificationPreferenceListResponse)
async def list_preferences(
    current_user: User = Depends(require_permission("notifications.view", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    prefs = await service.get_preferences()
    return NotificationPreferenceListResponse(items=prefs)


@router.put(
    "/preferences/{notification_type}",
    response_model=NotificationPreferenceResponse,
)
async def update_preference(
    notification_type: NotificationType,
    data: NotificationPreferenceUpdate,
    current_user: User = Depends(require_permission("notifications.manage", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.update_preference(notification_type, data)


@router.post("/preferences/initialize", response_model=NotificationPreferenceListResponse)
async def initialize_preferences(
    current_user: User = Depends(require_permission("notifications.manage", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    await service.initialize_defaults()
    all_prefs = await service.get_preferences()
    return NotificationPreferenceListResponse(items=all_prefs)


# ─── Logs ───


@router.get("/logs/", response_model=NotificationLogListResponse)
async def list_logs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    notification_type: NotificationType | None = Query(None),
    status: NotificationStatus | None = Query(None),
    current_user: User = Depends(
        require_any_permission("notifications.view", "notifications.manage", hidden=True)
    ),
    service: NotificationService = Depends(get_notification_service),
):
    # DataScope: non-admins only see logs sent to themselves
    tenant_id = request.state.tenant_id
    scope = get_data_scope(current_user, tenant_id, "notifications")
    recipient_email = None if scope == DataScope.all else current_user.email

    logs, total = await service.list_logs(
        page=page,
        per_page=per_page,
        notification_type=notification_type,
        status=status,
        recipient_email=recipient_email,
    )
    return NotificationLogListResponse(
        items=logs, total=total, page=page, per_page=per_page
    )


@router.get("/logs/{log_id}", response_model=NotificationLogResponse)
async def get_log(
    log_id: uuid.UUID,
    current_user: User = Depends(require_permission("notifications.view", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.get_log(log_id)


# ─── In-App ───


@router.get("/in-app/", response_model=InAppNotificationListResponse)
async def list_in_app(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(require_permission("notifications.view", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    items, total = await service.list_in_app(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        unread_only=unread_only,
    )
    return InAppNotificationListResponse(
        items=items, total=total, page=page, per_page=per_page
    )


@router.get("/in-app/unread-count", response_model=InAppUnreadCount)
async def get_unread_count(
    current_user: User = Depends(require_permission("notifications.view", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    count = await service.get_unread_count(current_user.id)
    return InAppUnreadCount(count=count)


@router.put("/in-app/{notif_id}/read", response_model=InAppNotificationResponse)
async def mark_read(
    notif_id: uuid.UUID,
    current_user: User = Depends(require_permission("notifications.view", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.mark_read(notif_id, user_id=current_user.id)


@router.put("/in-app/read-all")
async def mark_all_read(
    current_user: User = Depends(require_permission("notifications.view", hidden=True)),
    service: NotificationService = Depends(get_notification_service),
):
    count = await service.mark_all_read(current_user.id)
    return {"marked_read": count}
