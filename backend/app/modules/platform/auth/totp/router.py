from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.middleware import get_client_ip
from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.auth.core.schemas import MessageResponse, TokenResponse
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.auth.totp.schemas import (
    DisableTwoFactor,
    PhoneVerifyRequest,
    PhoneVerifyResponse,
    SendEmailCodeRequest,
    SendEmailCodeResponse,
    SendSmsCodeRequest,
    SendSmsCodeResponse,
    TwoFactorSetupConfirmed,
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
    response_model=TwoFactorSetupConfirmed,
    dependencies=[Depends(rate_limit(10, 300, "rl:2fa-verify-setup"))],
)
async def verify_setup(
    data: TwoFactorVerifySetup,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    return await service.verify_2fa_setup(current_user, data.code, ip_address=ip, user_agent=ua)


@router.post(
    "/disable",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit(5, 3600, "rl:2fa-disable"))],
)
async def disable_2fa(
    data: DisableTwoFactor,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    await service.disable_2fa(current_user, data.password, ip_address=ip, user_agent=ua)
    return MessageResponse(message="Tweefactorauthenticatie is uitgeschakeld")



@router.post(
    "/send-email-code",
    response_model=SendEmailCodeResponse,
    dependencies=[Depends(rate_limit(3, 180, "rl:2fa-email"))],
)
async def send_email_code(
    data: SendEmailCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    verification_id = await service.send_2fa_email_code(
        data.two_factor_token, data.purpose, ip_address=ip, user_agent=ua,
    )
    return SendEmailCodeResponse(
        verification_id=verification_id,
        message="Verificatiecode verstuurd naar je e-mailadres",
    )


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
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    return await service.verify_2fa_login(
        data.two_factor_token, data.code,
        method=data.method, verification_id=data.verification_id,
        ip_address=ip, user_agent=ua,
    )


@router.post(
    "/send-sms-code",
    response_model=SendSmsCodeResponse,
    dependencies=[Depends(rate_limit(3, 180, "rl:2fa-sms"))],
)
async def send_sms_code(
    data: SendSmsCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    verification_id = await service.send_2fa_sms_code(
        data.two_factor_token, data.purpose, ip_address=ip, user_agent=ua,
    )
    return SendSmsCodeResponse(
        verification_id=verification_id,
        message="Verificatiecode verstuurd via SMS",
    )


@router.post(
    "/phone/request-verify",
    response_model=SendSmsCodeResponse,
    dependencies=[Depends(rate_limit(3, 300, "rl:phone-verify"))],
)
async def request_phone_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    verification_id = await service.request_phone_verification(
        current_user, ip_address=ip, user_agent=ua,
    )
    return SendSmsCodeResponse(
        verification_id=verification_id,
        message="Verificatiecode verstuurd naar je telefoonnummer",
    )


@router.post(
    "/phone/verify",
    response_model=PhoneVerifyResponse,
    dependencies=[Depends(rate_limit(10, 300, "rl:phone-verify-code"))],
)
async def verify_phone(
    data: PhoneVerifyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = TOTPService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    await service.verify_phone(
        current_user, data.verification_id, data.code,
        ip_address=ip, user_agent=ua,
    )
    return PhoneVerifyResponse(
        message="Telefoonnummer succesvol geverifieerd",
        phone_verified=True,
    )
