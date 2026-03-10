"""Tests for brute force login protection (login_throttle)."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.login_throttle import (
    _attempt_key,
    _memory_attempts,
    _memory_check,
    _memory_record,
    check_login_allowed,
    clear_failed_attempts,
    record_failed_attempt,
)


@pytest.fixture(autouse=True)
def _clear_memory():
    """Clear in-memory attempts between tests."""
    _memory_attempts.clear()
    yield
    _memory_attempts.clear()


def _make_redis_mock(zcard_return: int = 0) -> AsyncMock:
    """Create a Redis mock with pipeline support."""
    redis = AsyncMock()
    redis.zremrangebyscore = AsyncMock()
    redis.zcard = AsyncMock(return_value=zcard_return)
    redis.delete = AsyncMock()

    pipe = AsyncMock()
    pipe.zremrangebyscore = MagicMock(return_value=pipe)
    pipe.zadd = MagicMock(return_value=pipe)
    pipe.zcard = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[0, True, zcard_return, True])
    redis.pipeline = MagicMock(return_value=pipe)

    return redis


# ---------------------------------------------------------------------------
# _attempt_key
# ---------------------------------------------------------------------------

def test_attempt_key_hashes_email():
    key = _attempt_key("user@example.com")
    expected_hash = hashlib.sha256("user@example.com".encode()).hexdigest()[:16]
    assert key == f"login_fail:{expected_hash}"


def test_attempt_key_case_insensitive():
    assert _attempt_key("User@Example.COM") == _attempt_key("user@example.com")


# ---------------------------------------------------------------------------
# check_login_allowed — Redis path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_allowed_under_threshold():
    redis = _make_redis_mock(zcard_return=2)
    redis.zcard = AsyncMock(return_value=2)
    with patch("app.core.login_throttle.settings", login_max_attempts=5, login_lockout_seconds=900):
        result = await check_login_allowed("user@test.com", redis)
    assert result is True


@pytest.mark.asyncio
async def test_check_allowed_at_threshold():
    redis = _make_redis_mock(zcard_return=5)
    redis.zcard = AsyncMock(return_value=5)
    with patch("app.core.login_throttle.settings", login_max_attempts=5, login_lockout_seconds=900):
        result = await check_login_allowed("user@test.com", redis)
    assert result is False


# ---------------------------------------------------------------------------
# check_login_allowed — fallback paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_allowed_redis_none_fallback():
    with patch("app.core.login_throttle.settings", login_max_attempts=5, login_lockout_seconds=900):
        result = await check_login_allowed("user@test.com", None)
    assert result is True  # no attempts recorded yet


@pytest.mark.asyncio
async def test_check_allowed_redis_error_fallback():
    redis = AsyncMock()
    redis.zremrangebyscore = AsyncMock(side_effect=ConnectionError("down"))
    with patch("app.core.login_throttle.settings", login_max_attempts=5, login_lockout_seconds=900):
        result = await check_login_allowed("user@test.com", redis)
    assert result is True  # memory fallback, no attempts yet


# ---------------------------------------------------------------------------
# record_failed_attempt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_failed_returns_count():
    redis = _make_redis_mock(zcard_return=3)
    with patch("app.core.login_throttle.settings", login_max_attempts=5, login_lockout_seconds=900):
        count = await record_failed_attempt("user@test.com", redis)
    assert count == 3


@pytest.mark.asyncio
async def test_record_failed_redis_none_fallback():
    with patch("app.core.login_throttle.settings", login_max_attempts=5, login_lockout_seconds=900):
        count = await record_failed_attempt("user@test.com", None)
    assert count == 1


@pytest.mark.asyncio
async def test_record_failed_redis_error_fallback():
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.execute = AsyncMock(side_effect=ConnectionError("down"))
    redis.pipeline = MagicMock(return_value=pipe)
    with patch("app.core.login_throttle.settings", login_max_attempts=5, login_lockout_seconds=900):
        count = await record_failed_attempt("user@test.com", redis)
    assert count == 1  # memory fallback


# ---------------------------------------------------------------------------
# clear_failed_attempts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_attempts_redis():
    redis = AsyncMock()
    await clear_failed_attempts("user@test.com", redis)
    redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_clear_attempts_memory():
    key = _attempt_key("user@test.com")
    _memory_attempts[key] = [1.0, 2.0]
    await clear_failed_attempts("user@test.com", None)
    assert key not in _memory_attempts


# ---------------------------------------------------------------------------
# In-memory functions
# ---------------------------------------------------------------------------

def test_memory_check_allows_under():
    assert _memory_check("test_key", max_attempts=5, window=900) is True


def test_memory_check_blocks_at_max():
    import time
    now = time.time()
    _memory_attempts["test_key"] = [now - i for i in range(5)]
    assert _memory_check("test_key", max_attempts=5, window=900) is False


def test_memory_record_evicts_at_limit():
    """When exceeding _MEMORY_MAX_KEYS, oldest key is evicted."""
    import time
    now = time.time()
    for i in range(5001):
        _memory_attempts[f"key_{i}"] = [now - 1000 + i]
    with patch("app.core.login_throttle.settings", login_lockout_seconds=900):
        _memory_record("new_key", window=900)
    assert len(_memory_attempts) <= 5001
