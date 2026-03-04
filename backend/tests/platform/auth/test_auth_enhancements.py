"""Tests for auth enhancement features (magic link, 2FA email, enhanced sessions)."""

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.core.security import (
    create_login_verify_token,
    decode_token,
)


# ---------------------------------------------------------------------------
# 1. Login verify token (magic link)
# ---------------------------------------------------------------------------


def test_create_login_verify_token():
    """Login verify token contains correct payload."""
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    token = create_login_verify_token(user_id, session_id)
    payload = decode_token(token)

    assert payload["type"] == "login_verify"
    assert payload["sub"] == str(user_id)
    assert payload["session_id"] == str(session_id)
    assert "exp" in payload
    assert "jti" in payload


def test_login_verify_token_expires():
    """Login verify token should expire after configured minutes."""
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    token = create_login_verify_token(user_id, session_id)
    payload = decode_token(token)

    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
    delta = exp - iat
    expected_minutes = settings.login_email_verification_expire_minutes
    assert abs(delta.total_seconds() - expected_minutes * 60) < 5


# ---------------------------------------------------------------------------
# 2. Verification code hashing (HMAC-SHA256)
# ---------------------------------------------------------------------------


def test_verification_code_hmac_hash():
    """Verification codes should be hashed with HMAC-SHA256."""
    code = "123456"
    expected = hmac.new(
        settings.secret_key.encode(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()

    # Import the actual function from the service
    from app.modules.platform.auth.verification.service import _hash_code

    actual = _hash_code(code)
    assert actual == expected


def test_verification_code_hmac_timing_safe():
    """Different codes produce different hashes."""
    from app.modules.platform.auth.verification.service import _hash_code

    h1 = _hash_code("123456")
    h2 = _hash_code("654321")
    assert h1 != h2


# ---------------------------------------------------------------------------
# 3. VerificationCodeService — create_and_send rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verification_code_cooldown():
    """create_and_send raises RateLimitError if called within cooldown."""
    from app.core.exceptions import RateLimitError
    from app.modules.platform.auth.verification.service import VerificationCodeService

    db = AsyncMock()

    # Simulate a recent code (created 30 seconds ago — within 60s cooldown)
    recent_code = MagicMock()
    recent_code.created_at = datetime.now(timezone.utc) - timedelta(seconds=30)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = recent_code
    db.execute = AsyncMock(return_value=result_mock)

    service = VerificationCodeService(db)

    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.full_name = "Test User"

    with pytest.raises(RateLimitError):
        await service.create_and_send(user, "email", "2fa_login")


# ---------------------------------------------------------------------------
# 4. VerificationCodeService — verify max attempts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verification_code_max_attempts():
    """verify raises AuthenticationError if max attempts exceeded."""
    from app.core.exceptions import AuthenticationError
    from app.modules.platform.auth.verification.service import VerificationCodeService

    db = AsyncMock()

    code_record = MagicMock()
    code_record.used = False
    code_record.attempts = settings.verification_code_max_attempts  # already at max
    code_record.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = code_record
    db.execute = AsyncMock(return_value=result_mock)

    service = VerificationCodeService(db)
    with pytest.raises(AuthenticationError, match="pogingen"):
        await service.verify(uuid.uuid4(), "123456")


@pytest.mark.asyncio
async def test_verification_code_expired():
    """verify raises AuthenticationError if code is expired."""
    from app.core.exceptions import AuthenticationError
    from app.modules.platform.auth.verification.service import VerificationCodeService

    db = AsyncMock()

    code_record = MagicMock()
    code_record.used = False
    code_record.attempts = 0
    code_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = code_record
    db.execute = AsyncMock(return_value=result_mock)

    service = VerificationCodeService(db)
    with pytest.raises(AuthenticationError, match="verlopen"):
        await service.verify(uuid.uuid4(), "123456")


# ---------------------------------------------------------------------------
# 5. parse_user_agent
# ---------------------------------------------------------------------------


def test_parse_user_agent_chrome_windows():
    """parse_user_agent extracts browser, OS, device_type for Chrome on Windows."""
    from app.core.security_emails import parse_user_agent

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    info = parse_user_agent(ua)
    assert info["browser"] == "Chrome"
    assert "Windows" in info["os"]
    assert info["device_type"] == "desktop"


def test_parse_user_agent_safari_iphone():
    """parse_user_agent detects mobile device."""
    from app.core.security_emails import parse_user_agent

    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
    info = parse_user_agent(ua)
    assert info["browser"] == "Safari"
    assert info["device_type"] == "mobile"


def test_parse_user_agent_ipad():
    """parse_user_agent detects tablet."""
    from app.core.security_emails import parse_user_agent

    ua = "Mozilla/5.0 (iPad; CPU OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
    info = parse_user_agent(ua)
    assert info["device_type"] == "tablet"


def test_parse_user_agent_none():
    """parse_user_agent handles None gracefully."""
    from app.core.security_emails import parse_user_agent

    info = parse_user_agent(None)
    assert info["browser"] == "Onbekend"
    assert info["os"] == "Onbekend"
    assert info["device_type"] == "desktop"


# ---------------------------------------------------------------------------
# 6. Email template generation
# ---------------------------------------------------------------------------


def test_build_login_verification_email():
    """Login verification email contains verify URL and user name."""
    from app.core.security_emails import build_login_verification_email

    subject, html = build_login_verification_email(
        "Jan Jansen",
        "https://example.com/auth/verify-session?token=abc123",
        "1.2.3.4",
        "Mozilla/5.0 Chrome/120",
    )
    assert "Bevestig" in subject
    assert "Jan Jansen" in html
    assert "verify-session?token=abc123" in html
    assert "1.2.3.4" in html
