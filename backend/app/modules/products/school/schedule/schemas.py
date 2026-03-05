import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.modules.products.school.schedule.models import LessonStatus


# --- LessonSlot ---


class LessonSlotCreate(BaseModel):
    student_id: uuid.UUID
    day_of_week: int = Field(ge=1, le=7)
    start_time: time
    duration_minutes: int = Field(default=30, ge=15, le=120)
    location: str | None = Field(None, max_length=255)
    teacher_user_id: uuid.UUID | None = None
    is_active: bool = True


class LessonSlotUpdate(BaseModel):
    day_of_week: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=120)
    location: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class LessonSlotResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    day_of_week: int
    start_time: time
    duration_minutes: int
    location: str | None
    teacher_user_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonSlotListResponse(BaseModel):
    items: list[LessonSlotResponse]
    total: int
    page: int
    per_page: int


# --- LessonInstance ---


class LessonInstanceCreate(BaseModel):
    student_id: uuid.UUID
    lesson_date: date
    start_time: time
    duration_minutes: int = Field(default=30, ge=15, le=120)
    lesson_slot_id: uuid.UUID | None = None
    teacher_user_id: uuid.UUID | None = None
    status: LessonStatus = LessonStatus.scheduled


class LessonInstanceUpdate(BaseModel):
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=120)
    status: LessonStatus | None = None


class LessonInstanceReschedule(BaseModel):
    new_date: date
    new_time: time
    reason: str | None = Field(None, max_length=500)


class LessonInstanceResponse(BaseModel):
    id: uuid.UUID
    lesson_slot_id: uuid.UUID | None
    student_id: uuid.UUID
    lesson_date: date
    start_time: time
    duration_minutes: int
    status: LessonStatus
    teacher_user_id: uuid.UUID | None
    substitute_teacher_user_id: uuid.UUID | None
    substitution_reason: str | None
    cancellation_reason: str | None
    rescheduled_to_date: date | None
    rescheduled_to_time: time | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonInstanceListResponse(BaseModel):
    items: list[LessonInstanceResponse]
    total: int
    page: int
    per_page: int


# --- Generate lessons ---


class GenerateLessonsRequest(BaseModel):
    start_date: date
    end_date: date


class GenerateLessonsResponse(BaseModel):
    generated: int
    skipped: int
    errors: list[str]


# --- Holiday ---


class HolidayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    description: str | None = Field(None, max_length=1000)
    is_recurring: bool = False


class HolidayUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(None, max_length=1000)
    is_recurring: bool | None = None


class HolidayResponse(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    description: str | None
    is_recurring: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HolidayListResponse(BaseModel):
    items: list[HolidayResponse]
    total: int
    page: int
    per_page: int


# --- Calendar ---


class SubstitutionCreate(BaseModel):
    substitute_teacher_user_id: uuid.UUID
    reason: str | None = Field(None, max_length=500)


class CalendarDayEntry(BaseModel):
    id: uuid.UUID
    student_name: str
    lesson_date: date
    start_time: time
    duration_minutes: int
    status: LessonStatus
    teacher_user_id: uuid.UUID | None = None
    substitute_teacher_user_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class CalendarWeekResponse(BaseModel):
    week_start: date
    week_end: date
    lessons: list[CalendarDayEntry]
    holidays: list[HolidayResponse]
