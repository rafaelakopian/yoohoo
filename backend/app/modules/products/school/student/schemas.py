import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    date_of_birth: date | None = None
    lesson_day: str | None = Field(None, max_length=20)
    lesson_duration: int | None = Field(None, ge=15, le=120)
    lesson_time: str | None = Field(None, max_length=10)
    level: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    student_number: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=255)
    invoice_email: str | None = Field(None, max_length=255)
    invoice_cc_email: str | None = Field(None, max_length=255)
    invoice_discount: str | None = Field(None, max_length=100)
    iban: str | None = Field(None, max_length=34)
    bic: str | None = Field(None, max_length=11)
    account_holder_name: str | None = Field(None, max_length=255)
    account_holder_city: str | None = Field(None, max_length=255)
    direct_debit: bool = False
    guardian_name: str | None = Field(None, max_length=255)
    guardian_relationship: str | None = Field(None, max_length=50)
    guardian_phone: str | None = Field(None, max_length=50)
    guardian_phone_work: str | None = Field(None, max_length=50)
    guardian_email: str | None = Field(None, max_length=255)


class StudentUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=255)
    last_name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    date_of_birth: date | None = None
    lesson_day: str | None = Field(None, max_length=20)
    lesson_duration: int | None = Field(None, ge=15, le=120)
    lesson_time: str | None = Field(None, max_length=10)
    level: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    is_active: bool | None = None
    student_number: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=255)
    invoice_email: str | None = Field(None, max_length=255)
    invoice_cc_email: str | None = Field(None, max_length=255)
    invoice_discount: str | None = Field(None, max_length=100)
    iban: str | None = Field(None, max_length=34)
    bic: str | None = Field(None, max_length=11)
    account_holder_name: str | None = Field(None, max_length=255)
    account_holder_city: str | None = Field(None, max_length=255)
    direct_debit: bool | None = None
    guardian_name: str | None = Field(None, max_length=255)
    guardian_relationship: str | None = Field(None, max_length=50)
    guardian_phone: str | None = Field(None, max_length=50)
    guardian_phone_work: str | None = Field(None, max_length=50)
    guardian_email: str | None = Field(None, max_length=255)


class StudentResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str | None
    email: str | None
    phone: str | None
    date_of_birth: date | None
    lesson_day: str | None
    lesson_duration: int | None
    lesson_time: str | None
    level: str | None
    notes: str | None
    is_active: bool
    student_number: str | None
    address: str | None
    postal_code: str | None
    city: str | None
    invoice_email: str | None
    invoice_cc_email: str | None
    invoice_discount: str | None
    iban: str | None
    bic: str | None
    account_holder_name: str | None
    account_holder_city: str | None
    direct_debit: bool
    guardian_name: str | None
    guardian_relationship: str | None
    guardian_phone: str | None
    guardian_phone_work: str | None
    guardian_email: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudentListResponse(BaseModel):
    items: list[StudentResponse]
    total: int
    page: int
    per_page: int


class StudentImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


# --- Parent-Student Link schemas ---


class ParentStudentLinkCreate(BaseModel):
    user_id: uuid.UUID
    student_id: uuid.UUID
    relationship_type: str = Field("parent", max_length=50)


class ParentStudentLinkResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    student_id: uuid.UUID
    relationship_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ParentStudentLinkList(BaseModel):
    items: list[ParentStudentLinkResponse]


# --- Teacher-Student Assignment schemas ---


class TeacherStudentAssignmentCreate(BaseModel):
    user_id: uuid.UUID  # teacher's User.id
    notes: str | None = Field(None, max_length=500)


class TeacherStudentTransfer(BaseModel):
    from_teacher_user_id: uuid.UUID
    to_teacher_user_id: uuid.UUID


class TeacherStudentAssignmentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    student_id: uuid.UUID
    assigned_by_user_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeacherStudentAssignmentList(BaseModel):
    items: list[TeacherStudentAssignmentResponse]
