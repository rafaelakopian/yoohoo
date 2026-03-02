import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.tenant.attendance.models import AttendanceStatus


class AttendanceCreate(BaseModel):
    student_id: uuid.UUID
    lesson_date: date
    status: AttendanceStatus
    notes: str | None = Field(None, max_length=2000)
    recorded_by_user_id: uuid.UUID | None = None


class AttendanceUpdate(BaseModel):
    status: AttendanceStatus | None = None
    notes: str | None = Field(None, max_length=2000)


class AttendanceBulkItem(BaseModel):
    student_id: uuid.UUID
    status: AttendanceStatus
    notes: str | None = Field(None, max_length=2000)


class AttendanceBulkCreate(BaseModel):
    lesson_date: date
    records: list[AttendanceBulkItem] = Field(min_length=1, max_length=500)


class AttendanceBulkResponse(BaseModel):
    created: int
    updated: int
    errors: list[str]


class AttendanceResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    lesson_date: date
    status: AttendanceStatus
    recorded_by_user_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AttendanceListResponse(BaseModel):
    items: list[AttendanceResponse]
    total: int
    page: int
    per_page: int
