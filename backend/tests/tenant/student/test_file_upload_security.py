"""Tests for file upload security validation (MIME type, file size, magic bytes)."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient



XLSX_MAGIC = b"\x50\x4b\x03\x04"
UPLOAD_URL = "/api/v1/org/test/students/import"


def _make_xlsx_content(size: int = 100) -> bytes:
    """Create fake XLSX content with valid magic bytes."""
    return XLSX_MAGIC + b"\x00" * (size - 4)


# ---------------------------------------------------------------------------
# MIME type validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_wrong_mime_rejected(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    content = _make_xlsx_content()
    files = {"file": ("test.txt", io.BytesIO(content), "text/plain")}
    resp = await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    assert resp.status_code == 200  # Returns 200 with error in body
    data = resp.json()
    assert data["imported"] == 0
    assert any("Excel" in e or "xlsx" in e or "xls" in e for e in data["errors"])


@pytest.mark.asyncio
async def test_upload_valid_mime_accepted(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Valid MIME + magic bytes should proceed to parse_excel."""
    content = _make_xlsx_content(200)
    files = {
        "file": (
            "students.xlsx",
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    with patch(
        "app.modules.products.school.student.router.parse_excel",
        return_value=([], []),
    ):
        resp = await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# File size validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_oversized_rejected(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    content = _make_xlsx_content(5 * 1024 * 1024 + 1)  # 5MB + 1 byte
    files = {
        "file": (
            "big.xlsx",
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    data = resp.json()
    assert data["imported"] == 0
    assert any("5MB" in e or "groot" in e for e in data["errors"])


# ---------------------------------------------------------------------------
# Magic bytes validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_invalid_magic_rejected(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    content = b"\x00\x00\x00\x00" + b"\x00" * 96  # Wrong magic
    files = {
        "file": (
            "fake.xlsx",
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    data = resp.json()
    assert data["imported"] == 0
    assert any("formaat" in e or "format" in e.lower() for e in data["errors"])


@pytest.mark.asyncio
async def test_upload_too_short_rejected(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    content = b"\x50\x4b"  # Only 2 bytes
    files = {
        "file": (
            "tiny.xlsx",
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    data = resp.json()
    assert data["imported"] == 0


@pytest.mark.asyncio
async def test_upload_valid_magic_calls_parser(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Valid magic bytes + MIME should call parse_excel."""
    content = _make_xlsx_content(200)
    mock_students = [{"first_name": "Test", "last_name": "Student"}]
    files = {
        "file": (
            "students.xlsx",
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    mock_result = AsyncMock()
    mock_result.imported = 1
    mock_result.skipped = 0
    mock_result.errors = []
    with patch(
        "app.modules.products.school.student.router.parse_excel",
        return_value=(mock_students, []),
    ) as mock_parse, patch(
        "app.modules.products.school.student.service.StudentService.bulk_import",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    mock_parse.assert_called_once()


@pytest.mark.asyncio
async def test_upload_empty_students_returns_error(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """parse_excel returning empty list should return error."""
    content = _make_xlsx_content(200)
    files = {
        "file": (
            "empty.xlsx",
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    with patch(
        "app.modules.products.school.student.router.parse_excel",
        return_value=([], ["Geen leerlingen gevonden"]),
    ):
        resp = await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    data = resp.json()
    assert data["imported"] == 0


# ---------------------------------------------------------------------------
# Auth checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_without_auth_rejected(tenant_client: AsyncClient):
    content = _make_xlsx_content()
    files = {"file": ("test.xlsx", io.BytesIO(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = await tenant_client.post(UPLOAD_URL, files=files)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_upload_no_content_type_bypasses_mime(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """When content_type is None, MIME check is skipped — documents a security gap."""
    content = _make_xlsx_content(200)
    # httpx sends no content-type when set to None
    files = {"file": ("test.xlsx", io.BytesIO(content), None)}
    with patch(
        "app.modules.products.school.student.router.parse_excel",
        return_value=([], []),
    ):
        resp = await tenant_client.post(UPLOAD_URL, files=files, headers=tenant_auth_headers)
    # File passes MIME check (skipped) but may fail on other validations
    assert resp.status_code == 200
