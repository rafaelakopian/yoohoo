"""Tests for middleware: get_client_ip, RequestID, SecurityHeaders, MaxBodySize."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from starlette.responses import Response

from app.core.middleware import (
    MaxBodySizeMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    get_client_ip,
)


def _make_request(headers=None, client_host="127.0.0.1"):
    """Create a mock Starlette Request."""
    request = MagicMock()
    request.headers = headers or {}
    if client_host:
        request.client = MagicMock()
        request.client.host = client_host
    else:
        request.client = None
    request.state = MagicMock()
    request.url.path = "/api/v1/test"
    return request


async def _noop_call_next(request):
    return Response(status_code=200)


# ===========================================================================
# get_client_ip
# ===========================================================================

def test_client_ip_forwarded_single():
    request = _make_request(headers={"X-Forwarded-For": "203.0.113.50"})
    assert get_client_ip(request) == "203.0.113.50"


def test_client_ip_forwarded_chain():
    request = _make_request(headers={"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"})
    assert get_client_ip(request) == "203.0.113.50"


def test_client_ip_forwarded_spaces():
    request = _make_request(headers={"X-Forwarded-For": "  203.0.113.50  , 70.41.3.18"})
    assert get_client_ip(request) == "203.0.113.50"


def test_client_ip_no_forwarded():
    request = _make_request(headers={}, client_host="192.168.1.1")
    assert get_client_ip(request) == "192.168.1.1"


def test_client_ip_no_client():
    request = _make_request(headers={}, client_host=None)
    assert get_client_ip(request) == "unknown"


# ===========================================================================
# RequestIDMiddleware
# ===========================================================================

@pytest.mark.asyncio
async def test_request_id_generates():
    """Generates UUID when X-Request-ID header is missing."""
    mw = RequestIDMiddleware(app=MagicMock())
    request = _make_request(headers={})
    with patch("app.core.middleware.structlog.contextvars") as mock_ctx:
        response = await mw.dispatch(request, _noop_call_next)
    assert "X-Request-ID" in response.headers
    # Verify it looks like a UUID
    rid = response.headers["X-Request-ID"]
    uuid.UUID(rid)  # Raises if not valid UUID


@pytest.mark.asyncio
async def test_request_id_preserves():
    """Preserves existing X-Request-ID header."""
    mw = RequestIDMiddleware(app=MagicMock())
    request = _make_request(headers={"X-Request-ID": "custom-id-123"})
    with patch("app.core.middleware.structlog.contextvars"):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.headers["X-Request-ID"] == "custom-id-123"


@pytest.mark.asyncio
async def test_request_id_in_response():
    """X-Request-ID is present in response headers."""
    mw = RequestIDMiddleware(app=MagicMock())
    request = _make_request(headers={})
    with patch("app.core.middleware.structlog.contextvars"):
        response = await mw.dispatch(request, _noop_call_next)
    assert "X-Request-ID" in response.headers


# ===========================================================================
# SecurityHeadersMiddleware
# ===========================================================================

@pytest.mark.asyncio
async def test_security_headers_all_present():
    """All 6 security headers are set."""
    mw = SecurityHeadersMiddleware(app=MagicMock())
    request = _make_request()
    response = await mw.dispatch(request, _noop_call_next)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "0"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_security_headers_no_overwrite():
    """setdefault() does not overwrite existing headers."""
    async def _call_next_with_headers(request):
        resp = Response(status_code=200)
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        return resp

    mw = SecurityHeadersMiddleware(app=MagicMock())
    request = _make_request()
    response = await mw.dispatch(request, _call_next_with_headers)
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"


@pytest.mark.asyncio
async def test_security_headers_values():
    """Verify exact header values match security policy."""
    mw = SecurityHeadersMiddleware(app=MagicMock())
    request = _make_request()
    response = await mw.dispatch(request, _noop_call_next)
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


# ===========================================================================
# MaxBodySizeMiddleware
# ===========================================================================

@pytest.mark.asyncio
async def test_max_body_allows_small():
    mw = MaxBodySizeMiddleware(app=MagicMock())
    request = _make_request(headers={"content-length": "1024"})
    with patch("app.core.middleware.settings", max_request_body_size=10_485_760):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_max_body_rejects_large():
    mw = MaxBodySizeMiddleware(app=MagicMock())
    request = _make_request(headers={"content-length": "20000000"})
    with patch("app.core.middleware.settings", max_request_body_size=10_485_760):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_max_body_no_content_length():
    """Missing content-length header should pass through."""
    mw = MaxBodySizeMiddleware(app=MagicMock())
    request = _make_request(headers={})
    with patch("app.core.middleware.settings", max_request_body_size=10_485_760):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_max_body_exact_limit():
    """Request exactly at limit should pass (> check, not >=)."""
    mw = MaxBodySizeMiddleware(app=MagicMock())
    request = _make_request(headers={"content-length": "10485760"})
    with patch("app.core.middleware.settings", max_request_body_size=10_485_760):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200
