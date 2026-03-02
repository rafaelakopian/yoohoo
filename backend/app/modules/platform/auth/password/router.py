from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.auth.core.schemas import MessageResponse
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.auth.password.schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.modules.platform.auth.password.service import PasswordService

router = APIRouter(prefix="/auth", tags=["auth-password"])


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(3, 3600, "rl:forgot"))],
)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_central_db),
):
    service = PasswordService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await service.request_password_reset(data.email, ip_address=ip, user_agent=ua)
    # Always same response to prevent email enumeration
    return MessageResponse(
        message="Als dit e-mailadres bij ons bekend is, ontvang je een e-mail met een resetlink."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(5, 3600, "rl:reset"))],
)
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_central_db),
):
    service = PasswordService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await service.reset_password(data.token, data.new_password, ip_address=ip, user_agent=ua)
    return MessageResponse(message="Wachtwoord succesvol gewijzigd. Je kunt nu inloggen.")


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    dependencies=[Depends(rate_limit(5, 300, "rl:change-pw"))],
)
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = PasswordService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return await service.change_password(
        current_user, data.current_password, data.new_password,
        ip_address=ip, user_agent=ua,
    )
