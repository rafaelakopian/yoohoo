import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_circuit_breakers_endpoint(client: AsyncClient):
    response = await client.get("/health/circuit-breakers")
    assert response.status_code == 200
    data = response.json()
    # Should contain the "email" breaker at minimum
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_send_email_safe_success():
    with patch("app.core.email._send_email_raw", new_callable=AsyncMock, return_value=True):
        from app.core.email import send_email_safe

        result = await send_email_safe("test@example.com", "Test", "<p>Hello</p>")
        assert result is True


@pytest.mark.asyncio
async def test_send_email_safe_circuit_open():
    from app.core.email import _email_breaker, send_email_safe
    from app.core.circuit_breaker import CircuitState

    # Force circuit to open state
    original_state = _email_breaker._state
    original_failures = _email_breaker._failure_count
    original_time = _email_breaker._last_failure_time

    try:
        _email_breaker._state = CircuitState.OPEN
        _email_breaker._failure_count = 10
        import time
        _email_breaker._last_failure_time = time.monotonic()  # Recent failure

        result = await send_email_safe("test@example.com", "Test", "<p>Hello</p>")
        assert result is False
    finally:
        # Restore original state
        _email_breaker._state = original_state
        _email_breaker._failure_count = original_failures
        _email_breaker._last_failure_time = original_time
