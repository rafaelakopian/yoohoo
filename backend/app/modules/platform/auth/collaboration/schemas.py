"""Schemas for collaboration management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.modules.platform.auth.core.schemas import GroupSummary


class CollaboratorResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    groups: list[GroupSummary] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteCollaborator(BaseModel):
    email: EmailStr
    group_id: uuid.UUID | None = None
