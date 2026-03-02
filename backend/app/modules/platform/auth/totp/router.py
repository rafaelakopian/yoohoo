from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.auth.core.schemas import MessageResponse, TokenResponse
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.auth.totp.schemas import (
    DisableTwoFactor,
    RegenerateBackupCodes,
    TwoFactorBackupCodes,
    TwoFactorSetupResponse,
    TwoFactorVerify,
    TwoFactorVerifySetup,
)
from app.modules.platform.auth.totp.service import TOTPService

router = APIRouter(prefix="/auth/2fa", tags=["auth-2fa"])


@router.post(
    "/setup",
    response_model=TwoFactorSetupResponse,
    dependencies=[Depends(rate_limit(5, 3600, "rl:2fa-setup"))],
)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    return await service.setup_2fa(current_user)


@router.post(
    "/verify-setup",
    response_model=TwoFactorBackupCodes,
    dependencies=[Depends(rate_limit(10, 300, "rl:2fa-verify-setup"))],
)
async def verify_setup(
    data: TwoFactorVerifySetup,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    return await service.verify_2fa_setup(current_user, data.code)


@router.post(
    "/disable",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(5, 3600, "rl:2fa-disable"))],
)
async def disable_2fa(
    data: DisableTwoFactor,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    await service.disable_2fa(current_user, data.password)
    return MessageResponse(message="Tweefactorauthenticatie is uitgeschakeld")


@router.post(
    "/regenerate-backup-codes",
    response_model=TwoFactorBackupCodes,
    dependencies=[Depends(rate_limit(3, 3600, "rl:2fa-regen"))],
)
async def regenerate_backup_codes(
    data: RegenerateBackupCodes,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    return await service.regenerate_backup_codes(current_user, data.password)


@router.post(
    "/verify",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(10, 300, "rl:2fa"))],
)
async def verify_2fa(
    data: TwoFactorVerify,
    request: Request,
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return await service.verify_2fa_login(
        data.two_factor_token, data.code, ip_address=ip, user_agent=ua
    )
