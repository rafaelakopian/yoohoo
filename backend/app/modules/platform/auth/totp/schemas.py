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


class DisableTwoFactor(BaseModel):
    password: str


class RegenerateBackupCodes(BaseModel):
    password: str
