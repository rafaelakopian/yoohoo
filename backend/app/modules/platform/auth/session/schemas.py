import uuid
from datetime import datetime

from pydantic import BaseModel


class DeviceInfo(BaseModel):
    browser: str
    os: str
    device_type: str  # 'desktop' | 'mobile' | 'tablet'


class SessionInfo(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    is_current: bool = False
    session_type: str = "persistent"
    device_info: DeviceInfo | None = None

    model_config = {"from_attributes": True}
