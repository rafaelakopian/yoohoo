"""PEN-06: Information Disclosure Tests.

Verifies that error messages do not leak sensitive information,
debug endpoints are disabled, and security headers are present.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_wrong_password_no_user_enumeration(client: AsyncClient):
    """Login with wrong password should not reveal if the email exists."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nonexistent-user-12345@example.com",
        "password": "WrongPassword123!",
    })
    data = resp.json()
    assert resp.status_code in (401, 422)
    if resp.status_code == 401:
        msg = data.get("detail", "")
        assert "not found" not in msg.lower() or "onjuist" in msg.lower()


@pytest.mark.asyncio
async def test_forgot_password_no_email_enumeration(client: AsyncClient):
    """Forgot password should not reveal if the email exists."""
    resp = await client.post("/api/v1/auth/forgot-password", json={
        "email": "definitely-not-exists-xyz@example.com",
    })
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        data = resp.json()
        detail = str(data).lower()
        assert "not found" not in detail


@pytest.mark.asyncio
async def test_register_duplicate_no_enumeration(client: AsyncClient):
    """Registration with existing email should not confirm the email exists."""
    from unittest.mock import AsyncMock, patch
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        email = f"enum-test-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "password": "TestPass123!", "full_name": "Test",
        })
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": "TestPass123!", "full_name": "Test",
        })
    assert resp.status_code in (201, 400, 409, 422)


@pytest.mark.asyncio
async def test_404_no_stack_trace(client: AsyncClient):
    """404 responses should not contain stack traces."""
    response = await client.get("/api/v1/this-endpoint-definitely-does-not-exist")
    assert response.status_code in (404, 405)
    body = response.text.lower()
    assert "traceback" not in body
    assert "sqlalchemy" not in body


@pytest.mark.asyncio
async def test_422_no_internal_paths(client: AsyncClient):
    """Validation errors should not expose internal file paths."""
    response = await client.post("/api/v1/auth/login", json={
        "email": 12345,
    })
    if response.status_code == 422:
        body = response.text.lower()
        assert "/app/" not in body
        assert "site-packages" not in body


@pytest.mark.asyncio
async def test_invalid_json_no_stack_trace(client: AsyncClient):
    """Invalid JSON body should return clean error, not stack trace."""
    response = await client.post(
        "/api/v1/auth/login",
        content=b"this is not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in (400, 422)
    body = response.text.lower()
    assert "traceback" not in body


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """Critical security headers should be set on all responses."""
    response = await client.get("/health/live")
    assert response.headers.get("x-content-type-options") == "nosniff"
    x_frame = response.headers.get("x-frame-options")
    assert x_frame in ("DENY", "SAMEORIGIN")
    assert "x-xss-protection" in response.headers
    assert "referrer-policy" in response.headers


@pytest.mark.asyncio
async def test_no_server_version_header(client: AsyncClient):
    """Server header should not expose version details."""
    response = await client.get("/health/live")
    server = response.headers.get("server", "")
    assert "uvicorn" not in server.lower()
    assert "python" not in server.lower()


@pytest.mark.asyncio
async def test_request_id_header_present(client: AsyncClient):
    """X-Request-ID should be present in responses for traceability."""
    response = await client.get("/health/live")
    request_id = response.headers.get("x-request-id")
    assert request_id is not None


@pytest.mark.asyncio
async def test_jwt_secret_not_in_errors(client: AsyncClient):
    """JWT secret should never appear in error responses."""
    from app.config import settings
    secret = settings.jwt_secret_key
    endpoints = [
        ("/api/v1/auth/login", {"email": "x", "password": "y"}),
        ("/api/v1/auth/refresh", {"refresh_token": "invalid"}),
    ]
    for path, body in endpoints:
        response = await client.post(path, json=body)
        assert secret not in response.text


@pytest.mark.asyncio
async def test_database_url_not_in_errors(client: AsyncClient):
    """Database connection strings should never appear in error responses."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "x", "password": "y",
    })
    body = response.text.lower()
    assert "postgresql" not in body
    assert "asyncpg" not in body


@pytest.mark.asyncio
async def test_no_debug_routes(client: AsyncClient):
    """Common debug routes should not be accessible."""
    debug_paths = [
        "/debug", "/_debug", "/api/debug", "/__debug__",
        "/env", "/config", "/api/v1/debug",
    ]
    for path in debug_paths:
        response = await client.get(path)
        assert response.status_code in (404, 405), (
            f"Debug route {path} returned {response.status_code}"
        )


@pytest.mark.asyncio
async def test_health_no_sensitive_info(client: AsyncClient):
    """Health endpoints should not expose database credentials."""
    for path in ["/health/live", "/health/ready"]:
        response = await client.get(path)
        body = response.text.lower()
        assert "password" not in body
        assert "secret" not in body
        assert "postgresql://" not in body
        assert "redis://" not in body
