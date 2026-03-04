import uuid

from pydantic import BaseModel


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code_uri: str


class TwoFactorVerifySetup(BaseModel):
    code: str


class TwoFactorBackupCodes(BaseModel):
    backup_codes: list[str]
    message: str


class TwoFactorVerify(BaseModel):
    two_factor_token: str
    code: str
    method: str = "totp"  # 'totp' | 'email'
    verification_id: uuid.UUID | None = None  # required when method='email'


class DisableTwoFactor(BaseModel):
    password: str


class RegenerateBackupCodes(BaseModel):
    password: str


class SendEmailCodeRequest(BaseModel):
    two_factor_token: str
    purpose: str = "2fa_login"  # '2fa_login' | '2fa_recovery'


class SendEmailCodeResponse(BaseModel):
    verification_id: uuid.UUID
    message: str
