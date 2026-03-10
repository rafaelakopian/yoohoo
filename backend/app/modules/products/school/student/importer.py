"""Student-specific import handler and duplicate finder.

Registers the "students" entity type with the shared importer registry.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.school.student.models import Student
from app.modules.shared.importer import FieldInfo, register


STUDENT_FIELDS = [
    FieldInfo(name="full_name", label="Volledige naam"),
    FieldInfo(name="first_name", label="Voornaam", required=True),
    FieldInfo(name="last_name", label="Achternaam"),
    FieldInfo(name="student_number", label="Leerlingennummer"),
    FieldInfo(name="email", label="E-mailadres"),
    FieldInfo(name="phone", label="Telefoonnummer"),
    FieldInfo(name="date_of_birth", label="Geboortedatum"),
    FieldInfo(name="address", label="Adres"),
    FieldInfo(name="postal_code", label="Postcode"),
    FieldInfo(name="city", label="Plaats"),
    FieldInfo(name="lesson_day", label="Lesdag"),
    FieldInfo(name="lesson_duration", label="Lesduur (min)"),
    FieldInfo(name="lesson_time", label="Lestijd"),
    FieldInfo(name="level", label="Niveau"),
    FieldInfo(name="notes", label="Notities"),
    FieldInfo(name="invoice_email", label="Factuur e-mailadres"),
    FieldInfo(name="invoice_cc_email", label="Factuur cc e-mailadres"),
    FieldInfo(name="invoice_discount", label="Factuurkorting"),
    FieldInfo(name="iban", label="IBAN"),
    FieldInfo(name="bic", label="BIC"),
    FieldInfo(name="account_holder_name", label="Naam rekeninghouder"),
    FieldInfo(name="account_holder_city", label="Plaats rekeninghouder"),
    FieldInfo(name="direct_debit", label="Incasseren"),
    FieldInfo(name="guardian_name", label="Ouder/voogd naam"),
    FieldInfo(name="guardian_relationship", label="Relatie ouder/voogd"),
    FieldInfo(name="guardian_phone", label="Telefoon ouder"),
    FieldInfo(name="guardian_phone_work", label="Telefoon werk ouder"),
    FieldInfo(name="guardian_email", label="E-mail ouder"),
]

# Virtual fields are not direct model columns
_VIRTUAL_FIELDS = {"full_name"}

# Fields that the handler sets directly on the Student model
_STUDENT_MODEL_FIELDS = {f.name for f in STUDENT_FIELDS} - _VIRTUAL_FIELDS


def _preprocess_mapped_data(mapped_data: dict[str, Any]) -> dict[str, Any]:
    """Preprocess mapped data: split full_name, parse direct_debit."""
    data = dict(mapped_data)

    # full_name → first_name + last_name
    if "full_name" in data and data["full_name"]:
        full = str(data["full_name"]).strip()
        parts = full.split(None, 1)
        if not data.get("first_name"):
            data["first_name"] = parts[0]
        if len(parts) > 1 and not data.get("last_name"):
            data["last_name"] = parts[1]
    data.pop("full_name", None)

    # direct_debit → boolean
    if "direct_debit" in data and data["direct_debit"] is not None:
        val = str(data["direct_debit"]).strip().lower()
        data["direct_debit"] = val in ("ja", "yes", "true", "1", "j", "y")

    return data


async def find_duplicate_student(
    mapped_data: dict[str, Any],
    db: AsyncSession,
) -> tuple[uuid.UUID | None, dict[str, Any] | None]:
    """Find an existing student matching the imported data.

    Priority: student_number → email exact → phone exact → full name exact.
    Returns (student_id, existing_data_snapshot) or (None, None).
    """
    data = _preprocess_mapped_data(mapped_data)

    student_number = data.get("student_number")
    email = data.get("email")
    phone = data.get("phone")
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip() if data.get("last_name") else ""

    student: Student | None = None

    # 1. Student number exact match — most reliable identifier
    if student_number:
        result = await db.execute(
            select(Student).where(
                Student.student_number == str(student_number).strip(),
                Student.is_active,
            )
        )
        student = result.scalar_one_or_none()
        # If student_number is present but no match, skip weaker matches.
        # Different student_numbers = different students, even with same email/phone
        # (siblings share parent contact info).
        if not student:
            return None, None

    # 4. Full name exact match (case-insensitive)
    if not student and first_name:
        query = select(Student).where(
            func.lower(Student.first_name) == first_name.lower(),
            Student.is_active,
        )
        if last_name:
            query = query.where(func.lower(Student.last_name) == last_name.lower())
        else:
            query = query.where(
                (Student.last_name.is_(None)) | (Student.last_name == "")
            )
        result = await db.execute(query)
        student = result.scalar_one_or_none()

    if student:
        snapshot = _student_to_snapshot(student)
        return student.id, snapshot

    return None, None


async def import_student(
    mapped_data: dict[str, Any],
    existing_id: uuid.UUID | None,
    strategy: str,
    existing_data: dict[str, Any] | None,
    db: AsyncSession,
) -> tuple[uuid.UUID, str, dict[str, Any] | None]:
    """Handle a single import row for the Student entity.

    Args:
        mapped_data: Field values from the imported file.
        existing_id: ID of a duplicate student (if found).
        strategy: "skip", "enrich", "replace", or "rollback".
        existing_data: Snapshot of the existing student before changes.
        db: Async database session.

    Returns:
        (entity_id, status, previous_data_snapshot)
        status is one of: "imported", "updated", "skipped", "rolled_back"
    """
    data = _preprocess_mapped_data(mapped_data)

    # --- Rollback ---
    if strategy == "rollback":
        if existing_id and existing_data:
            result = await db.execute(
                select(Student).where(Student.id == existing_id)
            )
            student = result.scalar_one_or_none()
            if student:
                # Restore previous data
                for field_name, value in existing_data.items():
                    if field_name in _STUDENT_MODEL_FIELDS:
                        setattr(student, field_name, value)
                await db.flush()
                return existing_id, "rolled_back", None
        elif existing_id:
            # Was newly imported — soft delete
            result = await db.execute(
                select(Student).where(Student.id == existing_id)
            )
            student = result.scalar_one_or_none()
            if student:
                student.is_active = False
                await db.flush()
                return existing_id, "rolled_back", None
        return existing_id or uuid.uuid4(), "rolled_back", None

    # --- No duplicate found: create new ---
    if not existing_id:
        student_data = {
            k: v for k, v in data.items() if k in _STUDENT_MODEL_FIELDS
        }
        # Convert lesson_duration to int if present
        if "lesson_duration" in student_data and student_data["lesson_duration"]:
            try:
                student_data["lesson_duration"] = int(float(student_data["lesson_duration"]))
            except (ValueError, TypeError):
                student_data.pop("lesson_duration", None)

        student = Student(**student_data)
        db.add(student)
        await db.flush()
        return student.id, "imported", None

    # --- Duplicate found: apply strategy ---
    if strategy == "skip":
        return existing_id, "skipped", None

    result = await db.execute(
        select(Student).where(Student.id == existing_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        return existing_id, "skipped", None

    previous_snapshot = _student_to_snapshot(student)

    if strategy == "enrich":
        # Only fill empty fields — never overwrite existing values
        changed = False
        for field_name, new_value in data.items():
            if field_name not in _STUDENT_MODEL_FIELDS:
                continue
            if not new_value:
                continue
            current_value = getattr(student, field_name, None)
            if current_value is None or (isinstance(current_value, str) and not current_value.strip()):
                if field_name == "lesson_duration":
                    try:
                        new_value = int(float(new_value))
                    except (ValueError, TypeError):
                        continue
                setattr(student, field_name, new_value)
                changed = True

        if changed:
            await db.flush()
            return existing_id, "updated", previous_snapshot
        return existing_id, "skipped", None

    if strategy == "replace":
        # Overwrite all fields with import data (except id, is_active, created_at)
        for field_name, new_value in data.items():
            if field_name not in _STUDENT_MODEL_FIELDS:
                continue
            if field_name == "lesson_duration" and new_value:
                try:
                    new_value = int(float(new_value))
                except (ValueError, TypeError):
                    continue
            setattr(student, field_name, new_value if new_value else None)
        await db.flush()
        return existing_id, "updated", previous_snapshot

    return existing_id, "skipped", None


def _student_to_snapshot(student: Student) -> dict[str, Any]:
    """Create a data snapshot of a student for rollback."""
    return {
        field_name: getattr(student, field_name, None)
        for field_name in _STUDENT_MODEL_FIELDS
    }


# --- Register with importer registry ---
register(
    entity_type="students",
    fields=STUDENT_FIELDS,
    handler=import_student,
    finder=find_duplicate_student,
    permission="students.import",
)
