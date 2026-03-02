"""Job retry utilities with exponential backoff and dead letter logging."""

import structlog
from arq import Retry

logger = structlog.get_logger()

# Backoff schedule: attempt 1 → 10s, attempt 2 → 30s, attempt 3 → 90s, attempt 4 → 270s
BACKOFF_BASE_SECONDS = 10
BACKOFF_MULTIPLIER = 3


class NonRetryableJobError(Exception):
    """Permanent failure that should NOT be retried."""

    pass


# ── Allowlist approach: only KNOWN transient errors are retried ──
# Unknown exceptions default to dead letter (safer than blind retry).

# Python builtins — network transient errors only
# Note: ConnectionError and TimeoutError are OSError subclasses, so we get
# the network-relevant parts of OSError without catching "disk full" or
# "permission denied" (which are also OSError but non-retryable).
_BUILTIN_RETRYABLE = (
    ConnectionError,  # ECONNREFUSED, ECONNRESET, ECONNABORTED, etc.
    TimeoutError,  # ETIMEDOUT
)

# aiosmtplib — transient SMTP errors (connection/timeout, NOT recipient/auth)
try:
    from aiosmtplib import (
        SMTPConnectError,
        SMTPConnectTimeoutError,
        SMTPReadTimeoutError,
        SMTPServerDisconnected,
        SMTPTimeoutError,
    )

    _SMTP_RETRYABLE: tuple[type[Exception], ...] = (
        SMTPServerDisconnected,
        SMTPConnectError,
        SMTPTimeoutError,
        SMTPConnectTimeoutError,
        SMTPReadTimeoutError,
    )
except ImportError:
    _SMTP_RETRYABLE = ()

# httpx — transport-level errors (timeout, network)
try:
    from httpx import ConnectError as HttpxConnectError
    from httpx import ConnectTimeout, NetworkError, PoolTimeout, ReadTimeout, WriteTimeout

    _HTTPX_RETRYABLE: tuple[type[Exception], ...] = (
        ConnectTimeout,
        ReadTimeout,
        WriteTimeout,
        PoolTimeout,
        HttpxConnectError,
        NetworkError,
    )
except ImportError:
    _HTTPX_RETRYABLE = ()

# redis — connection/timeout errors
try:
    from redis import BusyLoadingError
    from redis import ConnectionError as RedisConnectionError
    from redis import TimeoutError as RedisTimeoutError

    _REDIS_RETRYABLE: tuple[type[Exception], ...] = (
        RedisConnectionError,
        RedisTimeoutError,
        BusyLoadingError,
    )
except ImportError:
    _REDIS_RETRYABLE = ()

# Combined retryable allowlist
RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    _BUILTIN_RETRYABLE + _SMTP_RETRYABLE + _HTTPX_RETRYABLE + _REDIS_RETRYABLE
)


def _is_retryable(error: Exception) -> bool:
    """Check if an error is retryable (known transient infra errors only).

    Uses allowlist approach: only explicitly listed transient exceptions are retried.
    NonRetryableJobError and unknown exceptions go straight to dead letter.
    """
    if isinstance(error, NonRetryableJobError):
        return False
    return isinstance(error, RETRYABLE_EXCEPTIONS)


def calculate_backoff(job_try: int) -> int:
    """Exponential backoff: base * multiplier ^ (attempt - 1)."""
    return BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** (job_try - 1))


def retry_or_fail(
    job_try: int,
    max_tries: int,
    error: Exception,
    job_name: str,
    **context: object,
) -> None:
    """Call from a job's except block. Raises Retry if attempts remain, otherwise logs dead letter.

    Allowlist approach: only known transient errors (ConnectionError, TimeoutError,
    SMTPServerDisconnected, httpx.NetworkError, redis.ConnectionError, etc.) are retried.
    Everything else (ValueError, SMTPRecipientsRefused, unknown errors) goes directly
    to dead letter.
    """
    if not _is_retryable(error):
        logger.warning(
            "job.non_retryable",
            job=job_name,
            error_type=type(error).__name__,
            error=str(error),
        )
        log_dead_letter(job_name, str(error), job_try, **context)
        return

    if job_try < max_tries:
        defer = calculate_backoff(job_try)
        logger.warning(
            "job.retrying",
            job=job_name,
            attempt=job_try,
            max_tries=max_tries,
            defer_seconds=defer,
            error=str(error),
        )
        raise Retry(defer=defer)

    log_dead_letter(job_name, str(error), job_try, **context)


def log_dead_letter(job_name: str, error_msg: str, attempts: int, **context: object) -> None:
    """Log a failed job that has exhausted all retries (dead letter)."""
    from app.core.metrics import job_dead_letter_total

    job_dead_letter_total.labels(job_name=job_name).inc()
    logger.error(
        "job.dead_letter",
        job=job_name,
        error=error_msg,
        attempts=attempts,
        **context,
    )
