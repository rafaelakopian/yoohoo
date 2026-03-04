import uuid

from pydantic import BaseModel


class MemberGroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str | None  # None for viewers without staff permissions (privacy)
    groups: list[MemberGroupSummary]
    is_active: bool


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int
