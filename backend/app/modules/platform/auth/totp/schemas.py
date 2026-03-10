import uuid

from pydantic import BaseModel


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code_uri: str


class TwoFactorVerifySetup(BaseModel):
    code: str


class TwoFactorSetupConfirmed(BaseModel):
    message: str


class TwoFactorVerify(BaseModel):
    two_factor_token: str
    code: str
    method: str = "totp"  # 'totp' | 'email' | 'sms'
    verification_id: uuid.UUID | None = None  # required when method='email' or 'sms'


class DisableTwoFactor(BaseModel):
    password: str



class SendEmailCodeRequest(BaseModel):
    two_factor_token: str
    purpose: str = "2fa_login"  # '2fa_login' | '2fa_recovery'


class SendEmailCodeResponse(BaseModel):
    verification_id: uuid.UUID
    message: str


class PhoneVerifyRequest(BaseModel):
    code: str
    verification_id: uuid.UUID


class PhoneVerifyResponse(BaseModel):
    message: str
    phone_verified: bool


class SendSmsCodeRequest(BaseModel):
    two_factor_token: str
    purpose: str = "2fa_login"  # '2fa_login' | '2fa_recovery'


class SendSmsCodeResponse(BaseModel):
    verification_id: uuid.UUID
    message: str
