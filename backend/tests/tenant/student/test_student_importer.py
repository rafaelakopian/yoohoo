"""Tests for the student-specific import handler and duplicate finder."""

import io

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.school.student.models import Student
from app.modules.products.school.student.importer import (
    find_duplicate_student,
    import_student,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_xlsx(headers: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _create_student(db: AsyncSession, **kwargs) -> Student:
    student = Student(**kwargs)
    db.add(student)
    await db.flush()
    return student


# ---------------------------------------------------------------------------
# Duplicate finder tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFindDuplicateStudent:
    async def test_find_by_email(self, tenant_db_session: AsyncSession):
        student = await _create_student(
            tenant_db_session, first_name="Jan", email="jan@test.nl"
        )

        found_id, snapshot = await find_duplicate_student(
            {"first_name": "Jan", "email": "jan@test.nl"}, tenant_db_session
        )

        assert found_id == student.id
        assert snapshot is not None
        assert snapshot["first_name"] == "Jan"

    async def test_find_by_email_case_insensitive(self, tenant_db_session: AsyncSession):
        student = await _create_student(
            tenant_db_session, first_name="Jan", email="JAN@Test.NL"
        )

        found_id, _ = await find_duplicate_student(
            {"first_name": "Jan", "email": "jan@test.nl"}, tenant_db_session
        )

        assert found_id == student.id

    async def test_find_by_name(self, tenant_db_session: AsyncSession):
        student = await _create_student(
            tenant_db_session, first_name="Maria", last_name="Bakker"
        )

        found_id, _ = await find_duplicate_student(
            {"first_name": "maria", "last_name": "bakker"}, tenant_db_session
        )

        assert found_id == student.id

    async def test_no_match(self, tenant_db_session: AsyncSession):
        await _create_student(
            tenant_db_session, first_name="Sophie"
        )

        found_id, snapshot = await find_duplicate_student(
            {"first_name": "Unknown", "email": "x@y.com"}, tenant_db_session
        )

        assert found_id is None
        assert snapshot is None


# ---------------------------------------------------------------------------
# Import handler tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestImportStudent:
    async def test_create_new_student(self, tenant_db_session: AsyncSession):
        entity_id, status, prev = await import_student(
            {"first_name": "Emma", "last_name": "de Jong", "email": "emma@test.nl"},
            None,  # no existing
            "skip",
            None,
            tenant_db_session,
        )

        assert status == "imported"
        assert prev is None

        student = await tenant_db_session.get(Student, entity_id)
        assert student is not None
        assert student.first_name == "Emma"
        assert student.email == "emma@test.nl"

    async def test_enrich_fills_empty_fields(self, tenant_db_session: AsyncSession):
        existing = await _create_student(
            tenant_db_session, first_name="Jan", email="jan@test.nl"
        )

        entity_id, status, prev = await import_student(
            {"first_name": "Jan", "email": "jan@test.nl", "phone": "0612345678"},
            existing.id,
            "enrich",
            {"first_name": "Jan", "email": "jan@test.nl", "phone": None},
            tenant_db_session,
        )

        assert status == "updated"
        assert prev is not None
        assert prev["phone"] is None  # previous was empty

        await tenant_db_session.refresh(existing)
        assert existing.phone == "0612345678"  # now filled

    async def test_enrich_does_not_overwrite(self, tenant_db_session: AsyncSession):
        existing = await _create_student(
            tenant_db_session, first_name="Jan", email="original@test.nl"
        )

        entity_id, status, _ = await import_student(
            {"first_name": "Jan", "email": "new@test.nl"},
            existing.id,
            "enrich",
            {"first_name": "Jan", "email": "original@test.nl"},
            tenant_db_session,
        )

        await tenant_db_session.refresh(existing)
        assert existing.email == "original@test.nl"  # NOT overwritten

    async def test_replace_overwrites(self, tenant_db_session: AsyncSession):
        existing = await _create_student(
            tenant_db_session, first_name="Jan", email="old@test.nl", phone="111"
        )

        entity_id, status, prev = await import_student(
            {"first_name": "Jan", "email": "new@test.nl", "phone": "222"},
            existing.id,
            "replace",
            {"first_name": "Jan", "email": "old@test.nl", "phone": "111"},
            tenant_db_session,
        )

        assert status == "updated"
        assert prev["email"] == "old@test.nl"

        await tenant_db_session.refresh(existing)
        assert existing.email == "new@test.nl"
        assert existing.phone == "222"

    async def test_skip_does_nothing(self, tenant_db_session: AsyncSession):
        existing = await _create_student(
            tenant_db_session, first_name="Jan", email="jan@test.nl"
        )

        entity_id, status, prev = await import_student(
            {"first_name": "Jan"},
            existing.id,
            "skip",
            None,
            tenant_db_session,
        )

        assert status == "skipped"
        assert prev is None

    async def test_rollback_soft_deletes_new(self, tenant_db_session: AsyncSession):
        # First create via import
        entity_id, _, _ = await import_student(
            {"first_name": "NewStudent"},
            None,
            "skip",
            None,
            tenant_db_session,
        )

        # Rollback
        _, status, _ = await import_student(
            {},
            entity_id,
            "rollback",
            None,  # No previous data → was new
            tenant_db_session,
        )

        assert status == "rolled_back"
        student = await tenant_db_session.get(Student, entity_id)
        assert student.is_active is False

    async def test_rollback_restores_previous_data(self, tenant_db_session: AsyncSession):
        existing = await _create_student(
            tenant_db_session, first_name="Jan", email="old@test.nl"
        )

        # Import with replace
        entity_id, _, prev = await import_student(
            {"first_name": "Jan", "email": "new@test.nl"},
            existing.id,
            "replace",
            {"first_name": "Jan", "email": "old@test.nl"},
            tenant_db_session,
        )

        # Rollback
        await import_student(
            {},
            existing.id,
            "rollback",
            prev,  # Has previous data
            tenant_db_session,
        )

        await tenant_db_session.refresh(existing)
        assert existing.email == "old@test.nl"


# ---------------------------------------------------------------------------
# Full endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestImportEndpoints:
    async def test_preview_endpoint(
        self, tenant_client: AsyncClient, tenant_auth_headers: dict
    ):
        xlsx_data = _make_xlsx(
            ["Voornaam", "Achternaam", "Email"],
            [["Emma", "de Vries", "emma@test.nl"]],
        )

        response = await tenant_client.post(
            "/api/v1/org/test/students/import/preview",
            files={"file": ("students.xlsx", xlsx_data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 1
        assert "batch_id" in data
        assert len(data["detected_headers"]) >= 3
        assert len(data["available_fields"]) > 0
        assert len(data["preview_rows"]) == 1

    async def test_preview_csv_endpoint(
        self, tenant_client: AsyncClient, tenant_auth_headers: dict
    ):
        csv_data = "Voornaam,Achternaam\nAlice,Bakker\n".encode("utf-8")

        response = await tenant_client.post(
            "/api/v1/org/test/students/import/preview",
            files={"file": ("students.csv", csv_data, "text/csv")},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 1

    async def test_full_import_flow(
        self, tenant_client: AsyncClient, tenant_auth_headers: dict
    ):
        """Test full flow: preview → execute → history → detail."""
        xlsx_data = _make_xlsx(
            ["Voornaam", "Achternaam"],
            [["Flow", "Test"], ["Flow2", "Test2"]],
        )

        # 1. Preview
        preview_resp = await tenant_client.post(
            "/api/v1/org/test/students/import/preview",
            files={"file": ("test.xlsx", xlsx_data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=tenant_auth_headers,
        )
        assert preview_resp.status_code == 200
        batch_id = preview_resp.json()["batch_id"]

        # 2. Execute
        execute_resp = await tenant_client.post(
            f"/api/v1/org/test/students/import/{batch_id}/execute",
            json={
                "column_mapping": {"Voornaam": "first_name", "Achternaam": "last_name"},
                "duplicate_strategy": "skip",
            },
            headers=tenant_auth_headers,
        )
        assert execute_resp.status_code == 200
        result = execute_resp.json()
        assert result["imported_count"] == 2
        assert result["status"] == "completed"

        # 3. History
        history_resp = await tenant_client.get(
            "/api/v1/org/test/students/import/history",
            headers=tenant_auth_headers,
        )
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert history["total"] >= 1

        # 4. Detail
        detail_resp = await tenant_client.get(
            f"/api/v1/org/test/students/import/history/{batch_id}",
            headers=tenant_auth_headers,
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["batch"]["id"] == batch_id
        assert len(detail["records"]) == 2

    async def test_rollback_endpoint(
        self, tenant_client: AsyncClient, tenant_auth_headers: dict
    ):
        xlsx_data = _make_xlsx(["Voornaam"], [["Rollback"]])

        preview_resp = await tenant_client.post(
            "/api/v1/org/test/students/import/preview",
            files={"file": ("rb.xlsx", xlsx_data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=tenant_auth_headers,
        )
        batch_id = preview_resp.json()["batch_id"]

        await tenant_client.post(
            f"/api/v1/org/test/students/import/{batch_id}/execute",
            json={"column_mapping": {"Voornaam": "first_name"}, "duplicate_strategy": "skip"},
            headers=tenant_auth_headers,
        )

        rollback_resp = await tenant_client.post(
            f"/api/v1/org/test/students/import/history/{batch_id}/rollback",
            headers=tenant_auth_headers,
        )
        assert rollback_resp.status_code == 200
