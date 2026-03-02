import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionInfo(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    is_current: bool = False

    model_config = {"from_attributes": True}
