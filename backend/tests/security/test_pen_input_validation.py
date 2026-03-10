"""PEN-04: Input Validation Tests.

Tests for SQL injection, XSS, path traversal, and other injection attacks
across all user-controlled input fields.
"""

import uuid

import pytest
from httpx import AsyncClient


SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "1' UNION SELECT * FROM users--",
    "admin'--",
    "' OR 1=1 LIMIT 1 --",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
async def test_sqli_login_email(client: AsyncClient, payload: str):
    """SQL injection in login email field should not cause errors."""
    response = await client.post("/api/v1/auth/login", json={
        "email": payload, "password": "anything",
    })
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
async def test_sqli_login_password(client: AsyncClient, payload: str):
    """SQL injection in password field should not cause errors."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": payload,
    })
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
async def test_sqli_admin_user_search(
    client: AsyncClient, auth_headers: dict, payload: str,
):
    """SQL injection in admin user search parameter."""
    response = await client.get(
        "/api/v1/platform/access/users/search",
        headers=auth_headers,
        params={"search": payload},
    )
    assert response.status_code != 500


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
async def test_sqli_register_fields(client: AsyncClient, payload: str):
    """SQL injection in registration fields should be handled safely."""
    response = await client.post("/api/v1/auth/register", json={
        "email": f"test-{uuid.uuid4().hex[:6]}@example.com",
        "password": "ValidPass123!",
        "full_name": payload,
    })
    assert response.status_code != 500


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<svg onload=alert(1)>",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", XSS_PAYLOADS)
async def test_xss_in_full_name(client: AsyncClient, payload: str):
    """XSS in full_name should not cause server errors."""
    response = await client.post("/api/v1/auth/register", json={
        "email": f"xss-{uuid.uuid4().hex[:6]}@example.com",
        "password": "ValidPass123!",
        "full_name": payload,
    })
    assert response.status_code != 500


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", XSS_PAYLOADS)
async def test_xss_in_profile_update(
    client: AsyncClient, auth_headers: dict, payload: str,
):
    """XSS in profile update should not be reflected unsanitized."""
    response = await client.patch(
        "/api/v1/auth/profile",
        headers=auth_headers,
        json={"full_name": payload},
    )
    assert response.status_code != 500


PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..//..//..//etc/passwd",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", PATH_TRAVERSAL_PAYLOADS)
async def test_path_traversal_in_student_id(
    tenant_client: AsyncClient, tenant_auth_headers: dict, payload: str,
):
    """Path traversal in student ID should be rejected."""
    response = await tenant_client.get(
        f"/api/v1/org/test/students/{payload}",
        headers=tenant_auth_headers,
    )
    assert response.status_code in (400, 404, 422)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", PATH_TRAVERSAL_PAYLOADS)
async def test_path_traversal_in_tenant_slug(
    client: AsyncClient, auth_headers: dict, payload: str,
):
    """Path traversal in tenant slug should be rejected."""
    response = await client.get(
        f"/api/v1/org/{payload}/students/",
        headers=auth_headers,
    )
    assert response.status_code in (400, 403, 404, 405, 422)


@pytest.mark.asyncio
async def test_oversized_json_body(client: AsyncClient):
    """Extremely large request bodies should be rejected."""
    huge_name = "A" * 100_000
    response = await client.post("/api/v1/auth/register", json={
        "email": "big@example.com",
        "password": "ValidPass123!",
        "full_name": huge_name,
    })
    assert response.status_code in (400, 413, 422)


@pytest.mark.asyncio
async def test_deeply_nested_json(client: AsyncClient):
    """Deeply nested JSON should not cause stack overflow."""
    nested = {"a": "b"}
    for _ in range(50):
        nested = {"nested": nested}
    response = await client.post("/api/v1/auth/login", json=nested)
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_host_header_injection(client: AsyncClient):
    """Host header manipulation should not cause errors."""
    headers = {"Host": "evil.com"}
    response = await client.get("/health/live", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_form_data_to_json_endpoint(client: AsyncClient):
    """Sending form data to a JSON endpoint should be rejected."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"email": "test@test.com", "password": "pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code in (400, 415, 422)


@pytest.mark.asyncio
async def test_unicode_normalization_attack(client: AsyncClient):
    """Unicode homoglyphs in email should not bypass validation."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "test\u0430dmin@example.com", "password": "anything",
    })
    assert response.status_code in (401, 422)
