import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.circuit_breaker import CircuitOpenError
from app.core.email import EmailSender, _resolve_sender


@pytest.mark.asyncio
async def test_circuit_breakers_endpoint(client: AsyncClient):
    response = await client.get("/health/circuit-breakers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def _mock_provider(succeed: bool = True, raise_circuit_open: bool = False):
    """Create a mock EmailProviderBase."""
    provider = MagicMock()
    if raise_circuit_open:
        provider.send = AsyncMock(side_effect=CircuitOpenError("test"))
    elif succeed:
        provider.send = AsyncMock(return_value=True)
    else:
        provider.send = AsyncMock(side_effect=RuntimeError("provider error"))
    provider.close = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_send_email_safe_success():
    """Primary provider succeeds → return True."""
    primary = _mock_provider(succeed=True)
    with patch("app.core.email._get_providers", return_value=(primary, None)):
        from app.core.email import send_email_safe

        result = await send_email_safe("test@example.com", "Test", "<p>Hello</p>")
        assert result is True
        primary.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_safe_circuit_open_no_fallback():
    """Primary circuit open, no fallback → return False."""
    primary = _mock_provider(raise_circuit_open=True)
    with patch("app.core.email._get_providers", return_value=(primary, None)):
        from app.core.email import send_email_safe

        result = await send_email_safe("test@example.com", "Test", "<p>Hello</p>")
        assert result is False


@pytest.mark.asyncio
async def test_send_email_safe_fallback_success():
    """Primary fails → fallback succeeds → return True."""
    primary = _mock_provider(succeed=False)
    fallback = _mock_provider(succeed=True)
    with patch("app.core.email._get_providers", return_value=(primary, fallback)):
        from app.core.email import send_email_safe

        result = await send_email_safe("test@example.com", "Test", "<p>Hello</p>")
        assert result is True
        primary.send.assert_called_once()
        fallback.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_safe_circuit_open_uses_fallback():
    """Primary circuit open → fallback called and succeeds."""
    primary = _mock_provider(raise_circuit_open=True)
    fallback = _mock_provider(succeed=True)
    with patch("app.core.email._get_providers", return_value=(primary, fallback)):
        from app.core.email import send_email_safe

        result = await send_email_safe("test@example.com", "Test", "<p>Hello</p>")
        assert result is True
        fallback.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_safe_primary_fails_no_fallback():
    """Primary fails, no fallback configured → return False."""
    primary = _mock_provider(succeed=False)
    with patch("app.core.email._get_providers", return_value=(primary, None)):
        from app.core.email import send_email_safe

        result = await send_email_safe("test@example.com", "Test", "<p>Hello</p>")
        assert result is False
        primary.send.assert_called_once()


# ---------------------------------------------------------------------------
# _resolve_sender tests
# ---------------------------------------------------------------------------

class TestResolveSender:
    """Tests for _resolve_sender() email sender resolution."""

    def test_account_with_config(self):
        """ACCOUNT sender with config values uses per-type from/name."""
        with patch("app.core.email.settings") as mock_settings:
            mock_settings.email_account_from = "account@yoohoo.nl"
            mock_settings.email_account_name = "Yoohoo Account"
            mock_settings.smtp_from = "noreply@yoohoo.nl"
            mock_settings.email_from_name = "Yoohoo"

            from_email, from_name = _resolve_sender(EmailSender.ACCOUNT)
            assert from_email == "account@yoohoo.nl"
            assert from_name == "Yoohoo Account"

    def test_security_fallback(self):
        """SECURITY sender without config falls back to defaults."""
        with patch("app.core.email.settings") as mock_settings:
            mock_settings.email_security_from = ""
            mock_settings.email_security_name = ""
            mock_settings.smtp_from = "noreply@yoohoo.nl"
            mock_settings.email_from_name = "Yoohoo"

            from_email, from_name = _resolve_sender(EmailSender.SECURITY)
            assert from_email == "noreply@yoohoo.nl"
            assert from_name == "Yoohoo"

    def test_none_uses_general(self):
        """None sender resolves to smtp_from / email_from_name."""
        with patch("app.core.email.settings") as mock_settings:
            mock_settings.smtp_from = "noreply@yoohoo.nl"
            mock_settings.email_from_name = "Yoohoo"

            from_email, from_name = _resolve_sender(None)
            assert from_email == "noreply@yoohoo.nl"
            assert from_name == "Yoohoo"

    def test_general_equals_none(self):
        """GENERAL and None produce the exact same result."""
        with patch("app.core.email.settings") as mock_settings:
            mock_settings.smtp_from = "noreply@yoohoo.nl"
            mock_settings.email_from_name = "Yoohoo"

            result_none = _resolve_sender(None)
            result_general = _resolve_sender(EmailSender.GENERAL)
            assert result_none == result_general


@pytest.mark.asyncio
async def test_send_email_job_invalid_sender_type():
    """Invalid sender_type string falls back to None (GENERAL), does not crash."""
    primary = _mock_provider(succeed=True)
    with (
        patch("app.core.email._get_providers", return_value=(primary, None)),
        patch("app.core.jobs.email.send_email_safe", new_callable=AsyncMock, return_value=True) as mock_send,
    ):
        from app.core.jobs.email import send_email_job

        result = await send_email_job(
            {"job_try": 1},
            to="test@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            sender_type="nonexistent_type",
        )
        assert result is True
        mock_send.assert_called_once_with(
            "test@example.com", "Test", "<p>Hello</p>", sender=None,
        )
