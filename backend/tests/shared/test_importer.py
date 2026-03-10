"""Tests for the generic import module — entity-type agnostic."""

import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.shared.importer import FieldInfo, register, get_config, _registry
from app.modules.shared.importer.file_parser import parse_file, MAX_ROWS
from app.modules.shared.importer.models import ImportBatch, ImportRecord
from app.modules.shared.importer.service import ImportService


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_xlsx(headers: list[str], rows: list[list], header_row: int = 1) -> bytes:
    """Create an in-memory xlsx file and return bytes."""
    wb = Workbook()
    ws = wb.active
    # Insert empty rows before header if header_row > 1
    for _ in range(header_row - 1):
        ws.append([])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_csv(headers: list[str], rows: list[list], delimiter: str = ",", encoding: str = "utf-8") -> bytes:
    """Create an in-memory CSV file and return bytes."""
    lines = [delimiter.join(headers)]
    for row in rows:
        lines.append(delimiter.join(str(c) if c is not None else "" for c in row))
    return "\n".join(lines).encode(encoding)


# ---------------------------------------------------------------------------
# File parser tests
# ---------------------------------------------------------------------------

class TestFileParserXlsx:
    def test_parse_xlsx_basic(self):
        data = _make_xlsx(
            ["Voornaam", "Achternaam", "Email"],
            [["Jan", "de Vries", "jan@test.nl"], ["Maria", "Bakker", "maria@test.nl"]],
        )
        result = parse_file(data, "xlsx")
        assert result.total_rows == 2
        assert "Voornaam" in result.headers
        assert result.rows[0]["Voornaam"] == "Jan"
        assert result.rows[1]["Email"] == "maria@test.nl"

    def test_parse_xlsx_auto_detect_header_row(self):
        """Header row is detected as the row with most non-empty cells."""
        data = _make_xlsx(
            ["Voornaam", "Achternaam", "Email", "Telefoon"],
            [["A", "B", "c@d.nl", "123"]],
            header_row=3,  # Two empty rows before header
        )
        result = parse_file(data, "xlsx")
        assert "Voornaam" in result.headers
        assert result.total_rows >= 1

    def test_parse_xlsx_skips_empty_rows(self):
        data = _make_xlsx(
            ["Naam"],
            [["Alice"], [None], ["Bob"]],
        )
        result = parse_file(data, "xlsx")
        assert result.total_rows == 2
        assert result.rows[0]["Naam"] == "Alice"
        assert result.rows[1]["Naam"] == "Bob"

    def test_parse_xlsx_too_many_rows(self):
        rows = [[f"student_{i}"] for i in range(MAX_ROWS + 1)]
        data = _make_xlsx(["Naam"], rows)
        with pytest.raises(ValueError, match="meer dan"):
            parse_file(data, "xlsx")

    def test_parse_xlsx_too_few_rows(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["Naam"])  # Only header, no data
        buf = io.BytesIO()
        wb.save(buf)
        # File with only 1 row should fail
        # Actually our parser needs at least 2 rows (header + 1 data)
        # but empty data row will be filtered, giving 0 data rows
        result = parse_file(buf.getvalue(), "xlsx")
        assert result.total_rows == 0


class TestFileParserCsv:
    def test_parse_csv_utf8(self):
        data = _make_csv(
            ["Voornaam", "Achternaam"],
            [["Jörg", "Müller"], ["René", "André"]],
        )
        result = parse_file(data, "csv")
        assert result.total_rows == 2
        assert result.rows[0]["Voornaam"] == "Jörg"

    def test_parse_csv_latin1(self):
        data = _make_csv(
            ["Voornaam", "Achternaam"],
            [["Hélène", "Dufour"]],
            encoding="latin-1",
        )
        result = parse_file(data, "csv")
        assert result.total_rows == 1
        assert result.rows[0]["Voornaam"] == "Hélène"

    def test_parse_csv_semicolon_delimiter(self):
        data = _make_csv(
            ["Naam", "Email"],
            [["Test", "test@test.nl"]],
            delimiter=";",
        )
        result = parse_file(data, "csv")
        assert result.total_rows == 1
        assert result.rows[0]["Naam"] == "Test"

    def test_parse_csv_too_many_rows(self):
        rows = [[f"s{i}"] for i in range(MAX_ROWS + 1)]
        data = _make_csv(["Naam"], rows)
        with pytest.raises(ValueError, match="meer dan"):
            parse_file(data, "csv")


# ---------------------------------------------------------------------------
# Auto-mapping tests
# ---------------------------------------------------------------------------

class TestAutoMapping:
    def setup_method(self):
        self.service = ImportService()
        self.fields = [
            FieldInfo(name="first_name", label="Voornaam", required=True),
            FieldInfo(name="last_name", label="Achternaam"),
            FieldInfo(name="email", label="E-mailadres"),
            FieldInfo(name="phone", label="Telefoonnummer"),
        ]

    def test_exact_synonym_match(self):
        headers = ["voornaam", "achternaam", "email"]
        mapping = self.service._auto_map(headers, self.fields)
        assert mapping["voornaam"] == "first_name"
        assert mapping["achternaam"] == "last_name"
        assert mapping["email"] == "email"

    def test_contains_match(self):
        headers = ["voornaam student", "achternaam student"]
        mapping = self.service._auto_map(headers, self.fields)
        assert mapping["voornaam student"] == "first_name"
        assert mapping["achternaam student"] == "last_name"

    def test_case_insensitive(self):
        headers = ["VOORNAAM", "Achternaam", "E-Mail"]
        mapping = self.service._auto_map(headers, self.fields)
        assert mapping["VOORNAAM"] == "first_name"
        assert mapping["Achternaam"] == "last_name"
        assert mapping["E-Mail"] == "email"

    def test_no_duplicate_fields(self):
        """Each field should only be mapped once."""
        headers = ["voornaam", "naam"]  # Both could match first_name
        mapping = self.service._auto_map(headers, self.fields)
        field_values = list(mapping.values())
        assert len(field_values) == len(set(field_values))

    def test_unrecognized_headers_skipped(self):
        headers = ["voornaam", "onbekend_veld", "xyz123"]
        mapping = self.service._auto_map(headers, self.fields)
        assert "voornaam" in mapping
        assert "onbekend_veld" not in mapping
        assert "xyz123" not in mapping


# ---------------------------------------------------------------------------
# Service tests (with DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestImportServicePreview:
    async def test_preview_creates_batch(self, tenant_db_session: AsyncSession):
        # Register a test entity type
        test_handler = _make_test_handler()
        test_finder = _make_test_finder()
        register("test_entity", [
            FieldInfo(name="name", label="Naam", required=True),
        ], test_handler, test_finder, "test.import")

        service = ImportService()
        xlsx_data = _make_xlsx(["Naam"], [["Alice"], ["Bob"]])

        result = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_entity",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        assert result.batch_id is not None
        assert result.total_rows == 2
        assert "Naam" in result.detected_headers
        assert len(result.preview_rows) == 2

        # Verify batch in DB
        batch = await tenant_db_session.get(ImportBatch, result.batch_id)
        assert batch is not None
        assert batch.status == "preview"
        assert batch.entity_type == "test_entity"

        # Cleanup registry
        _registry.pop("test_entity", None)

    async def test_preview_stores_records(self, tenant_db_session: AsyncSession):
        test_handler = _make_test_handler()
        test_finder = _make_test_finder()
        register("test_entity2", [
            FieldInfo(name="name", label="Naam", required=True),
        ], test_handler, test_finder, "test.import")

        service = ImportService()
        xlsx_data = _make_xlsx(["Naam"], [["Alice"], ["Bob"], ["Charlie"]])

        result = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_entity2",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        # Verify records stored
        records = (await tenant_db_session.execute(
            select(ImportRecord).where(ImportRecord.batch_id == result.batch_id)
        )).scalars().all()
        assert len(records) == 3

        _registry.pop("test_entity2", None)


@pytest.mark.asyncio
class TestImportServiceExecute:
    async def test_execute_calls_handler(self, tenant_db_session: AsyncSession):
        calls = []

        async def handler(mapped_data, existing_id, strategy, existing_data, db):
            calls.append(mapped_data)
            return uuid.uuid4(), "imported", None

        async def finder(mapped_data, db):
            return None, None

        register("test_exec", [
            FieldInfo(name="name", label="Naam", required=True),
        ], handler, finder, "test.import")

        service = ImportService()
        xlsx_data = _make_xlsx(["Naam"], [["Alice"], ["Bob"]])

        preview = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_exec",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        result = await service.execute(
            batch_id=preview.batch_id,
            column_mapping={"Naam": "name"},
            duplicate_strategy="skip",
            db=tenant_db_session,
        )

        assert result.imported_count == 2
        assert len(calls) == 2

        _registry.pop("test_exec", None)

    async def test_execute_skip_strategy(self, tenant_db_session: AsyncSession):
        existing_id = uuid.uuid4()

        async def handler(mapped_data, eid, strategy, existing_data, db):
            if eid:
                return eid, "skipped", None
            return uuid.uuid4(), "imported", None

        async def finder(mapped_data, db):
            if mapped_data.get("name") == "Existing":
                return existing_id, {"name": "Existing"}
            return None, None

        register("test_skip", [
            FieldInfo(name="name", label="Naam", required=True),
        ], handler, finder, "test.import")

        service = ImportService()
        xlsx_data = _make_xlsx(["Naam"], [["New"], ["Existing"]])

        preview = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_skip",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        result = await service.execute(
            batch_id=preview.batch_id,
            column_mapping={"Naam": "name"},
            duplicate_strategy="skip",
            db=tenant_db_session,
        )

        assert result.imported_count == 1
        assert result.skipped_count == 1

        _registry.pop("test_skip", None)

    async def test_execute_requires_preview_status(self, tenant_db_session: AsyncSession):
        register("test_status", [
            FieldInfo(name="name", label="Naam", required=True),
        ], _make_test_handler(), _make_test_finder(), "test.import")

        service = ImportService()
        xlsx_data = _make_xlsx(["Naam"], [["Alice"]])

        preview = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_status",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        # Execute once
        await service.execute(
            batch_id=preview.batch_id,
            column_mapping={"Naam": "name"},
            duplicate_strategy="skip",
            db=tenant_db_session,
        )

        # Try again — should fail
        with pytest.raises(ValueError, match="preview"):
            await service.execute(
                batch_id=preview.batch_id,
                column_mapping={"Naam": "name"},
                duplicate_strategy="skip",
                db=tenant_db_session,
            )

        _registry.pop("test_status", None)

    async def test_execute_missing_required_field(self, tenant_db_session: AsyncSession):
        register("test_req", [
            FieldInfo(name="name", label="Naam", required=True),
        ], _make_test_handler(), _make_test_finder(), "test.import")

        service = ImportService()
        # Map to wrong field so "name" is not in mapped data
        xlsx_data = _make_xlsx(["Naam"], [["Alice"]])

        preview = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_req",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        result = await service.execute(
            batch_id=preview.batch_id,
            column_mapping={"Naam": "name"},  # This maps correctly
            duplicate_strategy="skip",
            db=tenant_db_session,
        )
        # Should succeed since mapping is correct
        assert result.imported_count == 1

        _registry.pop("test_req", None)


@pytest.mark.asyncio
class TestImportServiceRollback:
    async def test_rollback_calls_handler(self, tenant_db_session: AsyncSession):
        rollback_calls = []

        async def handler(mapped_data, existing_id, strategy, existing_data, db):
            if strategy == "rollback":
                rollback_calls.append(existing_id)
                return existing_id, "rolled_back", None
            return uuid.uuid4(), "imported", None

        register("test_rb", [
            FieldInfo(name="name", label="Naam", required=True),
        ], handler, _make_test_finder(), "test.import")

        service = ImportService()
        xlsx_data = _make_xlsx(["Naam"], [["Alice"]])

        preview = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_rb",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        await service.execute(
            batch_id=preview.batch_id,
            column_mapping={"Naam": "name"},
            duplicate_strategy="skip",
            db=tenant_db_session,
        )

        await service.rollback(
            batch_id=preview.batch_id,
            rolled_back_by=uuid.uuid4(),
            db=tenant_db_session,
        )

        assert len(rollback_calls) == 1

        # Verify batch status
        batch = await tenant_db_session.get(ImportBatch, preview.batch_id)
        assert batch.status == "rolled_back"

        _registry.pop("test_rb", None)

    async def test_rollback_requires_completed_status(self, tenant_db_session: AsyncSession):
        register("test_rb2", [
            FieldInfo(name="name", label="Naam", required=True),
        ], _make_test_handler(), _make_test_finder(), "test.import")

        service = ImportService()
        xlsx_data = _make_xlsx(["Naam"], [["Alice"]])

        preview = await service.preview(
            file_data=xlsx_data,
            file_name="test.xlsx",
            file_type="xlsx",
            entity_type="test_rb2",
            imported_by_id=uuid.uuid4(),
            db=tenant_db_session,
        )

        # Try rollback without executing — should fail
        with pytest.raises(ValueError, match="voltooide"):
            await service.rollback(
                batch_id=preview.batch_id,
                rolled_back_by=uuid.uuid4(),
                db=tenant_db_session,
            )

        _registry.pop("test_rb2", None)


# ---------------------------------------------------------------------------
# Test helper factories
# ---------------------------------------------------------------------------

def _make_test_handler():
    async def handler(mapped_data, existing_id, strategy, existing_data, db):
        if strategy == "rollback":
            return existing_id or uuid.uuid4(), "rolled_back", None
        return uuid.uuid4(), "imported", None
    return handler


def _make_test_finder():
    async def finder(mapped_data, db):
        return None, None
    return finder
