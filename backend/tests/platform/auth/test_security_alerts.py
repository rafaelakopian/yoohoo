"""Tests for security alerts: device fingerprinting, new device email,
2FA lifecycle emails, and admin 2FA reset."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_emails import (
    _normalize_ua,
    build_2fa_admin_reset_email,
    build_2fa_disabled_email,
    build_2fa_enabled_email,
    build_backup_code_used_email,
    build_new_device_email,
    compute_device_fingerprint,
)
from app.modules.platform.auth.models import User

TEST_TOTP_SECRET = "JBSWY3DPEHPK3PXP"


# --- Helper fixtures ---


@pytest_asyncio.fixture
async def regular_user(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Register a regular (non-superadmin) verified user WITHOUT 2FA."""
    data = {
        "email": f"regular-{uuid.uuid4().hex[:8]}@example.com",
        "password": "RegularPass123!",
        "full_name": "Regular User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json=data)
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    await db_session.execute(
        update(User).where(User.id == uuid.UUID(user_id)).values(
            email_verified=True,
            is_superadmin=False,
        )
    )
    await db_session.flush()

    return {**data, "id": user_id}


async def _login_regular(client: AsyncClient, email: str, password: str) -> dict:
    """Login helper for non-2FA users."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return resp.json()


# =====================================================================
# UA Normalization Tests
# =====================================================================


class TestUANormalization:
    def test_chrome_windows(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        assert _normalize_ua(ua) == "chrome/120 windows"

    def test_firefox_linux(self):
        ua = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
        assert _normalize_ua(ua) == "firefox/121 linux"

    def test_safari_macos(self):
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/17.2"
        assert _normalize_ua(ua) == "safari/17 macos"

    def test_chrome_android(self):
        ua = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36"
        assert _normalize_ua(ua) == "chrome/120 android"

    def test_safari_iphone(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
        assert _normalize_ua(ua) == "safari/604 ios"

    def test_none_ua(self):
        assert _normalize_ua(None) == "unknown"

    def test_empty_ua(self):
        assert _normalize_ua("") == "unknown"

    def test_minor_version_change_same_fingerprint(self):
        """Minor browser updates should produce the same fingerprint."""
        ua1 = "Mozilla/5.0 Chrome/120.0.0.0 Windows"
        ua2 = "Mozilla/5.0 Chrome/120.0.6099.230 Windows"
        assert compute_device_fingerprint(ua1) == compute_device_fingerprint(ua2)

    def test_different_browser_different_fingerprint(self):
        """Different browsers should produce different fingerprints."""
        ua_chrome = "Mozilla/5.0 Chrome/120 Windows"
        ua_firefox = "Mozilla/5.0 Firefox/121 Windows"
        assert compute_device_fingerprint(ua_chrome) != compute_device_fingerprint(ua_firefox)


# =====================================================================
# Device Fingerprint Tests
# =====================================================================


class TestDeviceFingerprint:
    def test_fingerprint_is_64_chars(self):
        fp = compute_device_fingerprint("Chrome/120 Windows")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_deterministic(self):
        ua = "Mozilla/5.0 Chrome/120 Windows"
        assert compute_device_fingerprint(ua) == compute_device_fingerprint(ua)

    def test_fingerprint_none(self):
        fp = compute_device_fingerprint(None)
        assert len(fp) == 64


# =====================================================================
# New Device Alert Tests
# =====================================================================


class TestNewDeviceAlert:
    @pytest.mark.asyncio
    async def test_first_login_no_alert(
        self, client: AsyncClient, regular_user: dict,
    ):
        """First ever login should not trigger a device alert."""
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock) as mock_email:
            tokens = await _login_regular(client, regular_user["email"], regular_user["password"])
            assert "access_token" in tokens
            mock_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_on_different_browser(
        self, client: AsyncClient, regular_user: dict,
    ):
        """Login from a different browser should trigger an alert."""
        # First login (Chrome)
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": "Mozilla/5.0 Chrome/120 Windows"},
            )

        # Second login (Firefox) — should trigger alert
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock) as mock_email:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": "Mozilla/5.0 Firefox/121 Windows"},
            )
            assert resp.status_code == 200
            mock_email.assert_called_once()
            # Verify subject contains "Nieuwe inlog"
            call_args = mock_email.call_args
            assert "Nieuwe inlog" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_no_alert_on_known_browser(
        self, client: AsyncClient, regular_user: dict,
    ):
        """Login from same browser should NOT trigger an alert."""
        ua = "Mozilla/5.0 Chrome/120 Windows"
        # First login
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": ua},
            )

        # Second login (same UA)
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock) as mock_email:
            await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": ua},
            )
            mock_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_alert_ip_change_same_browser(
        self, client: AsyncClient, regular_user: dict,
    ):
        """IP change with same browser should NOT trigger an alert (UA-only fingerprint)."""
        ua = "Mozilla/5.0 Chrome/120 Windows"
        # First login
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": ua, "X-Forwarded-For": "1.2.3.4"},
            )

        # Second login from different IP but same UA
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock) as mock_email:
            await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": ua, "X-Forwarded-For": "5.6.7.8"},
            )
            mock_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_alert_does_not_block_login(
        self, client: AsyncClient, regular_user: dict,
    ):
        """Even if email sending fails, login should still succeed."""
        ua1 = "Mozilla/5.0 Chrome/120 Windows"
        ua2 = "Mozilla/5.0 Firefox/121 Windows"
        # First login
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": ua1},
            )

        # Second login — email fails but login succeeds
        with patch("app.core.security_emails.send_email_safe", side_effect=Exception("SMTP down")):
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
                headers={"User-Agent": ua2},
            )
            assert resp.status_code == 200
            assert "access_token" in resp.json()


# =====================================================================
# 2FA Security Email Tests
# =====================================================================


class Test2FASecurityEmails:
    @pytest.mark.asyncio
    async def test_2fa_enabled_email_sent(
        self, client: AsyncClient, regular_user: dict, db_session: AsyncSession,
    ):
        """When 2FA is verified/enabled, a notification email is sent."""
        # Login
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            tokens = await _login_regular(client, regular_user["email"], regular_user["password"])
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Setup 2FA
        setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=headers)
        assert setup_resp.status_code == 200
        secret = setup_resp.json()["secret"]

        # Verify setup (this should send the email)
        totp = pyotp.TOTP(secret)
        with patch("app.modules.platform.auth.totp.service.send_email_safe", new_callable=AsyncMock) as mock_email:
            verify_resp = await client.post(
                "/api/v1/auth/2fa/verify-setup",
                json={"code": totp.now()},
                headers=headers,
            )
            assert verify_resp.status_code == 200
            mock_email.assert_called_once()
            assert "ingeschakeld" in mock_email.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_2fa_disabled_email_sent(
        self, client: AsyncClient, regular_user: dict, db_session: AsyncSession,
    ):
        """When 2FA is disabled, a notification email is sent."""
        # Login
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            tokens = await _login_regular(client, regular_user["email"], regular_user["password"])
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Setup and enable 2FA
        setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=headers)
        secret = setup_resp.json()["secret"]
        totp = pyotp.TOTP(secret)
        with patch("app.modules.platform.auth.totp.service.send_email_safe", new_callable=AsyncMock):
            await client.post(
                "/api/v1/auth/2fa/verify-setup",
                json={"code": totp.now()},
                headers=headers,
            )

        # Disable 2FA
        with patch("app.modules.platform.auth.totp.service.send_email_safe", new_callable=AsyncMock) as mock_email:
            disable_resp = await client.post(
                "/api/v1/auth/2fa/disable",
                json={"password": regular_user["password"]},
                headers=headers,
            )
            assert disable_resp.status_code == 200
            mock_email.assert_called_once()
            assert "uitgeschakeld" in mock_email.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_backup_code_used_email_sent(
        self, client: AsyncClient, regular_user: dict, db_session: AsyncSession,
    ):
        """When a backup code is used to log in, a notification email is sent."""
        # Login
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            tokens = await _login_regular(client, regular_user["email"], regular_user["password"])
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Setup and enable 2FA
        setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=headers)
        secret = setup_resp.json()["secret"]
        totp = pyotp.TOTP(secret)
        with patch("app.modules.platform.auth.totp.service.send_email_safe", new_callable=AsyncMock):
            verify_resp = await client.post(
                "/api/v1/auth/2fa/verify-setup",
                json={"code": totp.now()},
                headers=headers,
            )
        backup_codes = verify_resp.json()["backup_codes"]
        assert len(backup_codes) > 0

        # Login with 2FA (get 2fa token first)
        with patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": regular_user["email"], "password": regular_user["password"]},
            )
        assert login_resp.json().get("requires_2fa")
        two_factor_token = login_resp.json()["two_factor_token"]

        # Use backup code to verify
        with patch("app.modules.platform.auth.totp.service.send_email_safe", new_callable=AsyncMock) as mock_email, \
             patch("app.core.security_emails.send_email_safe", new_callable=AsyncMock):
            verify_resp = await client.post(
                "/api/v1/auth/2fa/verify",
                json={"two_factor_token": two_factor_token, "code": backup_codes[0]},
            )
            assert verify_resp.status_code == 200
            # Check backup code used email was sent
            mock_email.assert_called_once()
            assert "backup" in mock_email.call_args[0][1].lower()


# =====================================================================
# Email Template Tests
# =====================================================================


class TestEmailTemplates:
    def test_new_device_email_contains_context(self):
        subject, html = build_new_device_email(
            "Jan", "1.2.3.4", "Chrome/120 Windows", "https://example.com/sessions"
        )
        assert "Nieuwe inlog" in subject
        assert "1.2.3.4" in html
        assert "Chrome/120" in html
        assert "sessions" in html

    def test_2fa_enabled_email(self):
        subject, html = build_2fa_enabled_email("Jan", "1.2.3.4", "Firefox/121")
        assert "ingeschakeld" in subject
        assert "1.2.3.4" in html

    def test_2fa_disabled_email(self):
        subject, html = build_2fa_disabled_email("Jan")
        assert "uitgeschakeld" in subject

    def test_backup_code_used_email_low_count_warning(self):
        subject, html = build_backup_code_used_email("Jan", 1)
        assert "backup" in subject.lower()
        assert "1" in html
        # Should have warning for low count
        assert "Let op" in html

    def test_backup_code_used_email_no_warning(self):
        _, html = build_backup_code_used_email("Jan", 8)
        assert "Let op" not in html

    def test_admin_reset_email(self):
        subject, html = build_2fa_admin_reset_email("Jan")
        assert "gereset" in subject.lower()
        assert "beheerder" in html.lower()


# =====================================================================
# Admin 2FA Reset Tests
# =====================================================================


class TestAdmin2FAReset:
    @pytest.mark.asyncio
    async def test_admin_reset_2fa_success(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    ):
        """Admin can reset 2FA for another user."""
        # Create a user with 2FA enabled
        target_data = {
            "email": f"target-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TargetPass123!",
            "full_name": "Target User",
        }
        with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
            resp = await client.post("/api/v1/auth/register", json=target_data)
        target_id = resp.json()["id"]

        from app.modules.platform.auth.totp.service import _encrypt_secret
        await db_session.execute(
            update(User).where(User.id == uuid.UUID(target_id)).values(
                email_verified=True,
                totp_enabled=True,
                totp_secret_encrypted=_encrypt_secret(TEST_TOTP_SECRET),
                backup_codes_hash=json.dumps(["hash1", "hash2"]),
            )
        )
        await db_session.flush()

        # Admin resets 2FA
        with patch("app.modules.platform.admin.service.send_email_safe", new_callable=AsyncMock) as mock_email:
            resp = await client.post(
                f"/api/v1/admin/users/{target_id}/reset-2fa",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["totp_enabled"] is False
            # Email notification sent
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_reset_2fa_not_enabled(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    ):
        """Cannot reset 2FA if it's not enabled."""
        target_data = {
            "email": f"target-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TargetPass123!",
            "full_name": "Target User 2",
        }
        with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
            resp = await client.post("/api/v1/auth/register", json=target_data)
        target_id = resp.json()["id"]

        await db_session.execute(
            update(User).where(User.id == uuid.UUID(target_id)).values(email_verified=True)
        )
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/admin/users/{target_id}/reset-2fa",
            headers=auth_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_admin_reset_2fa_self_protection(
        self, client: AsyncClient, auth_headers: dict, verified_user: dict, db_session: AsyncSession,
    ):
        """Admin cannot reset their own 2FA."""
        # Get own user id
        me_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        my_id = me_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/admin/users/{my_id}/reset-2fa",
            headers=auth_headers,
        )
        assert resp.status_code == 403
