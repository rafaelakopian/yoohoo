import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, test_user_data: dict):
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["full_name"] == test_user_data["full_name"]
    assert data["email_verified"] is False
    assert "message" in data
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user_data: dict):
    """Duplicate registration returns 201 for anti-enumeration (no duplicate is created)."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json=test_user_data)
        response = await client.post("/api/v1/auth/register", json=test_user_data)
    # Anti-enumeration: returns 201 to prevent email discovery
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_login_unverified_user(client: AsyncClient, test_user_data: dict):
    """Login should fail for unverified users."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json=test_user_data)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]},
    )
    assert response.status_code == 401
    assert "geverifieerd" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login(client: AsyncClient, verified_user: dict, login_with_2fa):
    """Login should succeed for verified users (handles 2FA for superadmin)."""
    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])
    assert tokens["access_token"] is not None
    assert tokens["refresh_token"] is not None
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_token_contains_session_id(client: AsyncClient, verified_user: dict, login_with_2fa):
    """Access token should contain a session_id claim."""
    from app.core.security import decode_token

    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])
    payload = decode_token(tokens["access_token"])
    assert "session_id" in payload
    assert payload["session_id"] is not None
    # session_id should be a valid UUID string
    uuid.UUID(payload["session_id"])


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, verified_user: dict):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": verified_user["email"], "password": "WrongPassword123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient, verified_user: dict, login_with_2fa):
    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == verified_user["email"]
    assert data["email_verified"] is True


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, verified_user: dict, login_with_2fa):
    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])
    refresh_token = tokens["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Old token should be rotated (different from original)
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, verified_user: dict, login_with_2fa):
    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])
    refresh_token = tokens["refresh_token"]

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 204

    # Refresh should fail after logout
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401


# --- Email verification tests ---

@pytest.mark.asyncio
async def test_verify_email(client: AsyncClient, db_session, test_user_data: dict):
    """Full verification flow: register → get token from DB → verify."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=test_user_data)
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["id"]

    # Get the token hash from DB and generate matching token
    from app.modules.platform.auth.models import User
    from sqlalchemy import select
    result = await db_session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()
    assert user.verification_token_hash is not None

    # We need the raw token — re-register with known token via service
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.modules.platform.auth.core.service import _hash_token

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    user.verification_token_hash = token_hash
    user.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    await db_session.flush()

    # Verify
    response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 200
    assert "geverifieerd" in response.json()["message"].lower()

    # Now login should work
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    """Verify with invalid token should fail."""
    response = await client.post("/api/v1/auth/verify-email", json={"token": "invalid-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_resend_verification(client: AsyncClient, test_user_data: dict):
    """Resend verification should always return the same message."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json=test_user_data)

    # Resend for existing unverified user
    response = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": test_user_data["email"]},
    )
    assert response.status_code == 200
    msg1 = response.json()["message"]

    # Resend for non-existent email
    response = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 200
    msg2 = response.json()["message"]

    # Both messages should be the same (prevent email enumeration)
    assert msg1 == msg2


@pytest.mark.asyncio
async def test_verify_email_expired_token(client: AsyncClient, db_session, test_user_data: dict):
    """Verify with expired token should fail."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=test_user_data)
    user_id = reg_resp.json()["id"]

    import secrets
    from datetime import datetime, timedelta, timezone
    from app.modules.platform.auth.models import User
    from app.modules.platform.auth.core.service import _hash_token
    from sqlalchemy import select

    result = await db_session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()

    # Set expired token
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    user.verification_token_hash = token_hash
    user.verification_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()

    response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 401
    assert "verlopen" in response.json()["detail"].lower()


# --- Profile update tests ---


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, verified_user: dict, auth_headers: dict):
    """Authenticated user can update their profile name."""
    resp = await client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Nieuwe Naam"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Nieuwe Naam"

    # Verify via /me
    me_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_resp.json()["full_name"] == "Nieuwe Naam"


@pytest.mark.asyncio
async def test_update_profile_validation(client: AsyncClient, auth_headers: dict):
    """Profile update with empty name fails validation."""
    resp = await client.patch(
        "/api/v1/auth/profile",
        json={"full_name": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_profile_no_change(client: AsyncClient, verified_user: dict, auth_headers: dict):
    """Profile update with same name succeeds without error."""
    resp = await client.patch(
        "/api/v1/auth/profile",
        json={"full_name": verified_user["full_name"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_profile_unauthenticated(client: AsyncClient):
    """Unauthenticated profile update fails."""
    resp = await client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Hacker"},
    )
    assert resp.status_code == 401


# --- Email change tests ---


@pytest.mark.asyncio
async def test_request_email_change(client: AsyncClient, verified_user: dict, auth_headers: dict):
    """Authenticated user can request an email change."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/auth/request-email-change",
            json={"new_email": "newemail@example.com", "password": verified_user["password"]},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert "verificatie" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_request_email_change_wrong_password(client: AsyncClient, auth_headers: dict):
    """Request with wrong password fails."""
    resp = await client.post(
        "/api/v1/auth/request-email-change",
        json={"new_email": "newemail@example.com", "password": "wrongpassword"},
        headers=auth_headers,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_request_email_change_same_email(client: AsyncClient, verified_user: dict, auth_headers: dict):
    """Request with same email fails."""
    resp = await client.post(
        "/api/v1/auth/request-email-change",
        json={"new_email": verified_user["email"], "password": verified_user["password"]},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_request_email_change_duplicate_email(
    client: AsyncClient, verified_user: dict, auth_headers: dict, db_session
):
    """Request with an existing email returns 200 for anti-enumeration (no change initiated)."""
    # Register another user
    other_email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json={
            "email": other_email, "password": "OtherPass123!", "full_name": "Other",
        })

    resp = await client.post(
        "/api/v1/auth/request-email-change",
        json={"new_email": other_email, "password": verified_user["password"]},
        headers=auth_headers,
    )
    # Anti-enumeration: returns 200 to prevent email discovery
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_confirm_email_change(client: AsyncClient, verified_user: dict, auth_headers: dict, db_session):
    """Full email change flow: request → set token → confirm → login with new email."""
    import secrets
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.modules.platform.auth.models import User

    new_email = f"changed-{uuid.uuid4().hex[:8]}@example.com"

    # Request email change (sets pending fields in DB)
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/auth/request-email-change",
            json={"new_email": new_email, "password": verified_user["password"]},
            headers=auth_headers,
        )
    assert resp.status_code == 200

    # Get the pending token from DB and create a known one
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()
    assert user.pending_email == new_email

    # Set a known token
    raw_token = secrets.token_urlsafe(32)
    from app.modules.platform.auth.core.service import _hash_token
    token_hash = _hash_token(raw_token)
    user.pending_email_token_hash = token_hash
    user.pending_email_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    await db_session.flush()

    # Confirm email change
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/auth/confirm-email-change",
            json={"token": raw_token},
        )
    assert resp.status_code == 200
    assert "gewijzigd" in resp.json()["message"].lower()

    # Login with new email should work
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": new_email, "password": verified_user["password"]},
    )
    assert login_resp.status_code == 200

    # Login with old email should fail
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": verified_user["email"], "password": verified_user["password"]},
    )
    assert login_resp.status_code == 401


@pytest.mark.asyncio
async def test_confirm_email_change_invalid_token(client: AsyncClient):
    """Confirm with invalid token fails."""
    resp = await client.post(
        "/api/v1/auth/confirm-email-change",
        json={"token": "invalid-token-12345"},
    )
    assert resp.status_code == 401


# --- Password complexity tests ---


@pytest.mark.asyncio
async def test_register_weak_password_no_uppercase(client: AsyncClient):
    """Registration with password missing uppercase letter fails."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "weak@example.com", "password": "weakpass1!", "full_name": "Test",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password_no_digit(client: AsyncClient):
    """Registration with password missing digit fails."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "weak@example.com", "password": "WeakPass!!", "full_name": "Test",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password_no_special(client: AsyncClient):
    """Registration with password missing special character fails."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "weak@example.com", "password": "WeakPass12", "full_name": "Test",
    })
    assert resp.status_code == 422


# --- Account deletion tests ---


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient, verified_user: dict, auth_headers: dict, db_session):
    """Authenticated user can delete their own account."""
    resp = await client.post(
        "/api/v1/auth/delete-account",
        json={"password": verified_user["password"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "verwijderd" in resp.json()["message"].lower()

    # Login should fail after deletion
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": verified_user["email"], "password": verified_user["password"]},
    )
    assert login_resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_wrong_password(client: AsyncClient, auth_headers: dict):
    """Delete with wrong password fails."""
    resp = await client.post(
        "/api/v1/auth/delete-account",
        json={"password": "WrongPassword123!"},
        headers=auth_headers,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_unauthenticated(client: AsyncClient):
    """Unauthenticated delete fails."""
    resp = await client.post(
        "/api/v1/auth/delete-account",
        json={"password": "SomePass123!"},
    )
    assert resp.status_code == 401
