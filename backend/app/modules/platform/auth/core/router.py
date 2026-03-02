import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.dependencies import get_redis
from app.modules.platform.auth.dependencies import get_auth_service, get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.auth.core.schemas import (
    ConfirmEmailChange,
    DeleteAccount,
    GroupSummary,
    LoginResponse,
    MembershipResponse,
    MessageResponse,
    RefreshTokenRequest,
    RegisterResponse,
    RequestEmailChange,
    ResendVerificationRequest,
    TokenResponse,
    UpdateProfile,
    UserLogin,
    UserRegister,
    UserResponse,
    UserWithMemberships,
    VerifyEmailRequest,
)
from app.modules.platform.auth.core.service import AuthService
from app.modules.platform.auth.dependencies import get_effective_permissions

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    dependencies=[Depends(rate_limit(5, 3600, key_prefix="rl:register"))],
)
async def register(
    data: UserRegister,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(get_auth_service),
):
    user, token = await service.register(data)
    if user and token:
        background_tasks.add_task(service.send_verification_email, user, token)
    # Always return the same response to prevent email enumeration
    return RegisterResponse(
        id=user.id if user else uuid.uuid4(),
        email=data.email,
        full_name=data.full_name,
        email_verified=False,
        message="Registratie gelukt! Controleer je e-mail om je account te activeren.",
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    data: VerifyEmailRequest,
    service: AuthService = Depends(get_auth_service),
):
    await service.verify_email(data.token)
    return MessageResponse(message="E-mailadres succesvol geverifieerd! Je kunt nu inloggen.")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(3, 3600, key_prefix="rl:resend"))],
)
async def resend_verification(
    data: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(get_auth_service),
):
    token = await service.resend_verification(data.email)
    if token:
        # Fetch user to get full_name for email
        user = await service._get_user_by_email(data.email)
        if user:
            background_tasks.add_task(service.send_verification_email, user, token)
    # Always return the same response to prevent email enumeration
    return MessageResponse(
        message="Als dit e-mailadres bij ons bekend is, ontvang je een nieuwe verificatie-e-mail."
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit(10, 300, key_prefix="rl:login"))],
)
async def login(
    data: UserLogin,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    redis: aioredis.Redis | None = Depends(get_redis),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.login(
        data.email, data.password,
        ip_address=ip_address, user_agent=user_agent, redis=redis,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshTokenRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.refresh(data.refresh_token, ip_address=ip_address, user_agent=user_agent)


@router.post("/logout", status_code=204)
async def logout(
    data: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
):
    await service.logout(data.refresh_token)


@router.get("/me", response_model=UserWithMemberships)
async def me(current_user: User = Depends(get_current_user)):
    # Build enriched memberships with groups and effective permissions
    enriched_memberships = []
    for m in current_user.memberships:
        # Find groups for this tenant
        groups = []
        for a in current_user.group_assignments:
            if a.group.tenant_id == m.tenant_id:
                groups.append(GroupSummary(
                    id=a.group.id,
                    name=a.group.name,
                    slug=a.group.slug,
                ))

        # Calculate effective permissions for this tenant
        effective = sorted(get_effective_permissions(current_user, m.tenant_id))

        enriched_memberships.append(MembershipResponse(
            id=m.id,
            tenant_id=m.tenant_id,
            role=m.role,
            is_active=m.is_active,
            membership_type=m.membership_type,
            groups=groups,
            permissions=effective,
        ))

    # Build platform groups and permissions
    platform_groups = []
    platform_permissions_set: set[str] = set()
    for a in current_user.group_assignments:
        if a.group.tenant_id is None:
            platform_groups.append(GroupSummary(
                id=a.group.id,
                name=a.group.name,
                slug=a.group.slug,
            ))
            for gp in a.group.permissions:
                platform_permissions_set.add(gp.permission_codename)

    # Count remaining backup codes
    backup_codes_remaining = 0
    if current_user.totp_enabled and current_user.backup_codes_hash:
        import json
        try:
            codes = json.loads(current_user.backup_codes_hash)
            backup_codes_remaining = len(codes)
        except (json.JSONDecodeError, TypeError):
            pass

    return UserWithMemberships(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superadmin=current_user.is_superadmin,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
        memberships=enriched_memberships,
        platform_groups=platform_groups,
        platform_permissions=sorted(platform_permissions_set),
        totp_enabled=current_user.totp_enabled,
        backup_codes_remaining=backup_codes_remaining,
        last_login_at=current_user.last_login_at,
    )


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    data: UpdateProfile,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = AuthService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    user = await service.update_profile(current_user, data, ip_address=ip, user_agent=ua)
    return user


@router.post(
    "/request-email-change",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(3, 3600, key_prefix="rl:email-change"))],
)
async def request_email_change(
    data: RequestEmailChange,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = AuthService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    token = await service.request_email_change(current_user, data, ip_address=ip, user_agent=ua)
    # Only send verification if the email change was actually initiated (pending_email set)
    if current_user.pending_email:
        background_tasks.add_task(
            service.send_email_change_verification, current_user, data.new_email, token
        )
    # Always return the same response to prevent email enumeration
    return MessageResponse(
        message="Er is een verificatie-e-mail gestuurd naar je nieuwe adres. Controleer je inbox."
    )


@router.post(
    "/confirm-email-change",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(10, 3600, key_prefix="rl:confirm-email"))],
)
async def confirm_email_change(
    data: ConfirmEmailChange,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_central_db),
):
    service = AuthService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    user, old_email = await service.confirm_email_change(data.token, ip_address=ip, user_agent=ua)
    background_tasks.add_task(
        service.send_email_changed_notification, user.full_name, old_email
    )
    return MessageResponse(
        message="Je e-mailadres is succesvol gewijzigd. Log opnieuw in met je nieuwe adres."
    )


@router.post(
    "/delete-account",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(3, 3600, key_prefix="rl:delete-account"))],
)
async def delete_account(
    data: DeleteAccount,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = AuthService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await service.delete_account(current_user, data, ip_address=ip, user_agent=ua)
    return MessageResponse(message="Je account is verwijderd.")
