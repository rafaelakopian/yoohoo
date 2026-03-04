"""Schemas for verification code service."""

import uuid

from pydantic import BaseModel


class SendCodeResponse(BaseModel):
    verification_id: uuid.UUID
    message: str


class VerifyCodeRequest(BaseModel):
    verification_id: uuid.UUID
    code: str
