"""Brute force protection for login attempts.

Tracks failed login attempts per email (hashed) using Redis with in-memory fallback.
After N failed attempts, the account is locked for a configurable duration.
"""

import hashlib
import time
from collections import defaultdict

import structlog

from app.config import settings

logger = structlog.get_logger()

# In-memory fallback (used when Redis is unavailable)
_memory_attempts: dict[str, list[float]] = defaultdict(list)
_MEMORY_MAX_KEYS = 5_000


def _attempt_key(email: str) -> str:
    """Hash the email to avoid storing PII in Redis keys."""
    email_hash = hashlib.sha256(email.lower().encode()).hexdigest()[:16]
    return f"login_fail:{email_hash}"


async def check_login_allowed(email: str, redis) -> bool:
    """Check if login is allowed for this email. Returns False if locked out."""
    key = _attempt_key(email)
    max_attempts = settings.login_max_attempts
    window = settings.login_lockout_seconds

    if redis is None:
        return _memory_check(key, max_attempts, window)

    try:
        now = time.time()
        window_start = now - window
        # Count recent failures
        await redis.zremrangebyscore(key, 0, window_start)
        count = await redis.zcard(key)
        return count < max_attempts
    except Exception:
        logger.warning("login_throttle.redis_error", exc_info=True)
        return _memory_check(key, max_attempts, window)


async def record_failed_attempt(email: str, redis) -> int:
    """Record a failed login attempt. Returns the current count."""
    key = _attempt_key(email)
    window = settings.login_lockout_seconds

    if redis is None:
        return _memory_record(key, window)

    try:
        now = time.time()
        window_start = now - window
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[2]

        if count >= settings.login_max_attempts:
            logger.warning(
                "login_throttle.locked",
                email_hash=key,
                attempts=count,
            )
        return count
    except Exception:
        logger.warning("login_throttle.redis_error", exc_info=True)
        return _memory_record(key, window)


async def clear_failed_attempts(email: str, redis) -> None:
    """Clear failed attempts after successful login."""
    key = _attempt_key(email)

    if redis is None:
        _memory_attempts.pop(key, None)
        return

    try:
        await redis.delete(key)
    except Exception:
        logger.warning("login_throttle.redis_error", exc_info=True)
        _memory_attempts.pop(key, None)


def _memory_check(key: str, max_attempts: int, window: int) -> bool:
    now = time.time()
    window_start = now - window
    bucket = _memory_attempts.get(key, [])
    _memory_attempts[key] = [t for t in bucket if t > window_start]
    return len(_memory_attempts[key]) < max_attempts


def _memory_record(key: str, window: int) -> int:
    now = time.time()
    window_start = now - window
    bucket = _memory_attempts.get(key, [])
    _memory_attempts[key] = [t for t in bucket if t > window_start]
    _memory_attempts[key].append(now)
    # Evict oldest keys if too large
    if len(_memory_attempts) > _MEMORY_MAX_KEYS:
        oldest = min(_memory_attempts, key=lambda k: _memory_attempts[k][0] if _memory_attempts[k] else 0)
        del _memory_attempts[oldest]
    return len(_memory_attempts[key])
