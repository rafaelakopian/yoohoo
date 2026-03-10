"""Demo student definitions and creation logic."""

import sys
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.school.student.models import Student, TeacherStudentAssignment


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Student definitions per org (keyed by org slug suffix)
#   teacher=1 → docent1, teacher=2 → docent2
#   guardian=1 → ouder1, guardian=2 → ouder2
# ---------------------------------------------------------------------------

DEMO_STUDENTS: dict[str, list[dict]] = {
    "klankvlek": [
        {"first_name": "Emma", "last_name": "de Jong", "teacher": 1, "guardian": 1, "level": "gevorderd", "duration": 45},
        {"first_name": "Daan", "last_name": "Bakker", "teacher": 1, "guardian": 1, "level": "beginner", "duration": 30},
        {"first_name": "Sophie", "last_name": "Visser", "teacher": 1, "guardian": 2, "level": "intermediair", "duration": 30},
        {"first_name": "Liam", "last_name": "Smit", "teacher": 1, "guardian": 2, "level": "beginner", "duration": 30},
        {"first_name": "Julia", "last_name": "Mulder", "teacher": 1, "guardian": 1, "level": "gevorderd", "duration": 45},
        {"first_name": "Sem", "last_name": "de Vries", "teacher": 1, "guardian": 2, "level": "beginner", "duration": 30},
        {"first_name": "Anna", "last_name": "Peters", "teacher": 2, "guardian": 1, "level": "intermediair", "duration": 30},
        {"first_name": "Lucas", "last_name": "Meijer", "teacher": 2, "guardian": 1, "level": "beginner", "duration": 30},
        {"first_name": "Mila", "last_name": "van der Berg", "teacher": 2, "guardian": 2, "level": "gevorderd", "duration": 45},
        {"first_name": "Noah", "last_name": "Janssen", "teacher": 2, "guardian": 2, "level": "beginner", "duration": 30},
        {"first_name": "Eva", "last_name": "Hermans", "teacher": 2, "guardian": 1, "level": "intermediair", "duration": 45},
        {"first_name": "Finn", "last_name": "de Boer", "teacher": 2, "guardian": 2, "level": "beginner", "duration": 30},
    ],
    "hartman": [
        {"first_name": "Tess", "last_name": "Willems", "teacher": 1, "guardian": 1, "level": "gevorderd", "duration": 45},
        {"first_name": "Jesse", "last_name": "Bos", "teacher": 1, "guardian": 1, "level": "beginner", "duration": 30},
        {"first_name": "Sara", "last_name": "Dekker", "teacher": 1, "guardian": 2, "level": "intermediair", "duration": 30},
        {"first_name": "Luuk", "last_name": "van Dijk", "teacher": 1, "guardian": 2, "level": "beginner", "duration": 30},
        {"first_name": "Noor", "last_name": "Hendriks", "teacher": 2, "guardian": 1, "level": "gevorderd", "duration": 45},
        {"first_name": "Max", "last_name": "Scholten", "teacher": 2, "guardian": 1, "level": "beginner", "duration": 30},
        {"first_name": "Lotte", "last_name": "van Leeuwen", "teacher": 2, "guardian": 2, "level": "intermediair", "duration": 30},
        {"first_name": "Bram", "last_name": "Jansen", "teacher": 2, "guardian": 2, "level": "beginner", "duration": 30},
    ],
    "vos": [
        {"first_name": "Lisa", "last_name": "Vermeer", "teacher": 1, "guardian": 1, "level": "gevorderd", "duration": 45},
        {"first_name": "Thomas", "last_name": "Maas", "teacher": 1, "guardian": 1, "level": "beginner", "duration": 30},
        {"first_name": "Roos", "last_name": "de Graaf", "teacher": 1, "guardian": 2, "level": "intermediair", "duration": 30},
        {"first_name": "Thijs", "last_name": "Kok", "teacher": 2, "guardian": 2, "level": "beginner", "duration": 30},
        {"first_name": "Floor", "last_name": "van den Broek", "teacher": 2, "guardian": 1, "level": "gevorderd", "duration": 45},
        {"first_name": "Milan", "last_name": "Dijkstra", "teacher": 2, "guardian": 2, "level": "beginner", "duration": 30},
    ],
}


async def create_demo_students(
    db: AsyncSession,
    org_key: str,
    users: dict,
    owner_id: uuid.UUID,
) -> list[Student]:
    """Create demo students + teacher assignments in a tenant DB session.

    Returns list of created Student objects (with .id set).
    """
    student_defs = DEMO_STUDENTS[org_key]
    students: list[Student] = []

    for sdef in student_defs:
        teacher_key = f"docent{sdef['teacher']}"
        guardian_key = f"ouder{sdef['guardian']}"
        guardian_user = users.get(guardian_key)

        student = Student(
            first_name=sdef["first_name"],
            last_name=sdef["last_name"],
            level=sdef["level"],
            lesson_duration=sdef["duration"],
            is_active=True,
            guardian_name=guardian_user.full_name if guardian_user else None,
            guardian_email=guardian_user.email if guardian_user else None,
            guardian_relationship="ouder",
        )
        db.add(student)
        await db.flush()

        # Teacher assignment (teacher_user_id is from central DB)
        teacher_user = users[teacher_key]
        db.add(TeacherStudentAssignment(
            user_id=teacher_user.id,
            student_id=student.id,
            assigned_by_user_id=owner_id,
        ))

        students.append(student)

    await db.flush()
    _log(f"    {len(students)} leerlingen + docentkoppelingen aangemaakt")
    return students
