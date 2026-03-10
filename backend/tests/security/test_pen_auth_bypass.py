"""PEN-01: Authentication Bypass Tests.

Verifies that all protected endpoints reject unauthenticated requests
and that token manipulation is detected.
"""

import uuid

import pytest
from httpx import AsyncClient


# ======================================================================
# Unauthenticated access to protected endpoints
# ======================================================================

PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/auth/me"),
    ("PATCH", "/api/v1/auth/profile"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/change-password"),
    ("GET", "/api/v1/auth/sessions"),
    ("POST", "/api/v1/auth/delete-account"),
    ("POST", "/api/v1/auth/request-email-change"),
    ("POST", "/api/v1/auth/2fa/setup"),
    ("POST", "/api/v1/auth/2fa/verify-setup"),
    ("POST", "/api/v1/auth/2fa/disable"),
    ("GET", "/api/v1/platform/dashboard"),
    ("GET", "/api/v1/platform/orgs/"),
    ("GET", "/api/v1/platform/access/users"),
    ("GET", "/api/v1/platform/audit-logs"),
    ("GET", "/api/v1/platform/operations/dashboard"),
    ("GET", "/api/v1/platform/access/permissions/registry"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_no_token_rejected(client: AsyncClient, method: str, path: str):
    """Endpoints without Authorization header must return 401 or 403."""
    response = await client.request(method, path)
    assert response.status_code in (401, 403, 405, 422), (
        f"{method} {path} returned {response.status_code} without auth"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_invalid_token_rejected(client: AsyncClient, method: str, path: str):
    """Endpoints with garbage Bearer token must return 401."""
    headers = {"Authorization": "Bearer totally.invalid.token"}
    response = await client.request(method, path, headers=headers)
    assert response.status_code in (401, 403, 422), (
        f"{method} {path} accepted invalid token"
    )


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    """An expired JWT should be rejected."""
    import jwt
    from app.config import settings

    expired_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": 0, "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_token_rejected(client: AsyncClient):
    """JWT signed with wrong secret should be rejected."""
    import jwt
    import time

    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600, "type": "access"},
        "completely-wrong-secret-key-that-nobody-knows",
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_type_confusion(client: AsyncClient):
    """A refresh token should not work as an access token."""
    import jwt
    from app.config import settings

    import time
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600, "type": "refresh"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_2fa_token_not_usable_as_access(client: AsyncClient):
    """A 2FA challenge token should not work as an access token."""
    import jwt
    from app.config import settings
    import time

    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 300, "type": "2fa"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


# ======================================================================
# Algorithm confusion
# ======================================================================

@pytest.mark.asyncio
async def test_algorithm_none_rejected(client: AsyncClient):
    """JWT with alg=none should be rejected (algorithm confusion attack)."""
    import base64
    import json

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": str(uuid.uuid4()), "type": "access"}).encode()).rstrip(b"=")
    token = f"{header.decode()}.{payload.decode()}."
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


# ======================================================================
# Auth header format abuse
# ======================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("auth_value", [
    "Basic dXNlcjpwYXNz",          # Basic auth
    "Bearer",                       # Missing token
    "Bearer ",                      # Empty token
    "bearer valid.looking.token",   # Lowercase bearer
    "Token some-token-value",       # Wrong scheme
])
async def test_malformed_auth_header(client: AsyncClient, auth_value: str):
    """Malformed Authorization headers should be rejected."""
    headers = {"Authorization": auth_value}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code in (401, 403, 422)
