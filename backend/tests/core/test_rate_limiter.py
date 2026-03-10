"""Tests for rate limiting (per-IP global + per-tenant middleware and per-endpoint dependency)."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from app.core.rate_limiter import (
    RateLimitMiddleware,
    _memory_buckets,
    _memory_rate_check,
    rate_limit,
)


@pytest.fixture(autouse=True)
def _clear_buckets():
    _memory_buckets.clear()
    yield
    _memory_buckets.clear()


def _make_request(
    path="/api/v1/test",
    client_ip="1.2.3.4",
    redis=None,
    tenant_id=None,
):
    request = MagicMock()
    request.url.path = path
    request.headers = {}
    request.client = MagicMock()
    request.client.host = client_ip
    request.app.state.redis = redis
    request.state.tenant_id = tenant_id
    return request


def _make_redis_pipeline(zcard_return=1):
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.zremrangebyscore = MagicMock(return_value=pipe)
    pipe.zadd = MagicMock(return_value=pipe)
    pipe.zcard = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[0, True, zcard_return, True])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


async def _noop_call_next(request):
    return Response(status_code=200)


# ===========================================================================
# _memory_rate_check
# ===========================================================================

def test_memory_rate_allows_under_limit():
    assert _memory_rate_check("test", max_requests=5, window_seconds=60) is True


def test_memory_rate_blocks_at_limit():
    for _ in range(5):
        _memory_rate_check("test", max_requests=5, window_seconds=60)
    assert _memory_rate_check("test", max_requests=5, window_seconds=60) is False


def test_memory_rate_expires_old_entries():
    now = time.time()
    _memory_buckets["test"] = [now - 120, now - 90]
    assert _memory_rate_check("test", max_requests=5, window_seconds=60) is True
    assert len(_memory_buckets["test"]) == 1


def test_memory_rate_evicts_at_max_keys():
    now = time.time()
    for i in range(10001):
        _memory_buckets[f"k{i}"] = [now]
    _memory_rate_check("new_key", max_requests=100, window_seconds=60)
    assert len(_memory_buckets) <= 10001


# ===========================================================================
# rate_limit() dependency
# ===========================================================================

@pytest.mark.asyncio
async def test_rate_limit_dep_allows_redis():
    redis = _make_redis_pipeline(zcard_return=1)
    dep = rate_limit(max_requests=5, window_seconds=60)
    request = _make_request(redis=redis)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"):
        await dep(request)


@pytest.mark.asyncio
async def test_rate_limit_dep_blocks_redis_429():
    redis = _make_redis_pipeline(zcard_return=10)
    dep = rate_limit(max_requests=5, window_seconds=60)
    request = _make_request(redis=redis)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"):
        with pytest.raises(HTTPException) as exc_info:
            await dep(request)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_dep_no_redis_memory():
    dep = rate_limit(max_requests=5, window_seconds=60)
    request = _make_request(redis=None)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"):
        await dep(request)


@pytest.mark.asyncio
async def test_rate_limit_dep_redis_error_degrades():
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.execute = AsyncMock(side_effect=ConnectionError("down"))
    redis.pipeline = MagicMock(return_value=pipe)
    dep = rate_limit(max_requests=5, window_seconds=60)
    request = _make_request(redis=redis)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"):
        await dep(request)


# ===========================================================================
# RateLimitMiddleware
# ===========================================================================

@pytest.mark.asyncio
async def test_middleware_exempt_health():
    mw = RateLimitMiddleware(app=MagicMock())
    request = _make_request(path="/health/live")
    response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_middleware_exempt_metrics():
    mw = RateLimitMiddleware(app=MagicMock())
    request = _make_request(path="/metrics")
    response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_middleware_allows_under_limit():
    redis = _make_redis_pipeline(zcard_return=5)
    mw = RateLimitMiddleware(app=MagicMock())
    request = _make_request(redis=redis)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"),          patch("app.core.rate_limiter.settings", rate_limit_per_minute=60, rate_limit_per_tenant_per_minute=300):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_middleware_blocks_over_limit():
    redis = _make_redis_pipeline(zcard_return=100)
    mw = RateLimitMiddleware(app=MagicMock())
    request = _make_request(redis=redis)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"),          patch("app.core.rate_limiter.settings", rate_limit_per_minute=60, rate_limit_per_tenant_per_minute=300):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_middleware_no_redis_memory():
    mw = RateLimitMiddleware(app=MagicMock())
    request = _make_request(redis=None)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"),          patch("app.core.rate_limiter.settings", rate_limit_per_minute=60, rate_limit_per_tenant_per_minute=300):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_middleware_redis_error_degrades():
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.execute = AsyncMock(side_effect=ConnectionError("down"))
    redis.pipeline = MagicMock(return_value=pipe)
    mw = RateLimitMiddleware(app=MagicMock())
    request = _make_request(redis=redis)
    with patch("app.core.rate_limiter.get_client_ip", return_value="1.2.3.4"),          patch("app.core.rate_limiter.settings", rate_limit_per_minute=60, rate_limit_per_tenant_per_minute=300):
        response = await mw.dispatch(request, _noop_call_next)
    assert response.status_code == 200
