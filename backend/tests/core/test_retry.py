"""Tests for job retry utilities: backoff, retryable allowlist, dead letter."""

from unittest.mock import patch

import pytest
from arq import Retry

from app.core.jobs.retry import (
    NonRetryableJobError,
    _is_retryable,
    calculate_backoff,
    log_dead_letter,
    retry_or_fail,
)


# ─── calculate_backoff ───


def test_backoff_attempt_1():
    assert calculate_backoff(1) == 10


def test_backoff_attempt_2():
    assert calculate_backoff(2) == 30


def test_backoff_attempt_3():
    assert calculate_backoff(3) == 90


def test_backoff_attempt_4():
    assert calculate_backoff(4) == 270


# ─── _is_retryable (allowlist approach) ───


def test_connection_error_retryable():
    assert _is_retryable(ConnectionError("timeout")) is True


def test_timeout_error_retryable():
    assert _is_retryable(TimeoutError("timed out")) is True


def test_non_retryable_job_error():
    """NonRetryableJobError should never be retried."""
    assert _is_retryable(NonRetryableJobError("bad data")) is False


def test_value_error_not_retryable():
    """ValueError is not in the retryable allowlist."""
    assert _is_retryable(ValueError("invalid")) is False


def test_type_error_not_retryable():
    assert _is_retryable(TypeError("wrong type")) is False


def test_key_error_not_retryable():
    assert _is_retryable(KeyError("missing")) is False


def test_attribute_error_not_retryable():
    assert _is_retryable(AttributeError("no attr")) is False


def test_permission_error_not_retryable():
    """PermissionError (OSError subclass) should NOT be retried — disk/access issues."""
    assert _is_retryable(PermissionError("denied")) is False


def test_bare_os_error_not_retryable():
    """Bare OSError (disk full, etc.) should NOT be retried — too broad."""
    assert _is_retryable(OSError("No space left on device")) is False


def test_runtime_error_not_retryable():
    """RuntimeError is NOT in the retryable allowlist (unknown error → dead letter)."""
    assert _is_retryable(RuntimeError("transient")) is False


def test_unknown_exception_not_retryable():
    """Unknown exceptions should NOT be retried (safe default)."""
    assert _is_retryable(Exception("something unexpected")) is False


# ─── SMTP-specific retryable exceptions ───


def test_smtp_server_disconnected_retryable():
    from aiosmtplib import SMTPServerDisconnected

    assert _is_retryable(SMTPServerDisconnected("lost connection")) is True


def test_smtp_connect_error_retryable():
    from aiosmtplib import SMTPConnectError

    assert _is_retryable(SMTPConnectError("connection refused")) is True


def test_smtp_timeout_retryable():
    from aiosmtplib import SMTPTimeoutError

    assert _is_retryable(SMTPTimeoutError("timed out")) is True


def test_smtp_recipients_refused_not_retryable():
    """SMTPRecipientsRefused (bad recipient) should NOT be retried."""
    from aiosmtplib import SMTPRecipientsRefused

    assert _is_retryable(SMTPRecipientsRefused({"nobody@invalid.com": (550, "User unknown")})) is False


def test_smtp_auth_error_not_retryable():
    """SMTPAuthenticationError should NOT be retried."""
    from aiosmtplib import SMTPAuthenticationError

    assert _is_retryable(SMTPAuthenticationError(535, "bad credentials")) is False


# ─── retry_or_fail ───


def test_retry_or_fail_retryable_raises_retry():
    """Transient error with attempts remaining should raise arq.Retry."""
    with pytest.raises(Retry) as exc_info:
        retry_or_fail(
            job_try=1,
            max_tries=4,
            error=ConnectionError("connection refused"),
            job_name="test_job",
        )
    assert exc_info.value.defer_score == 10_000  # milliseconds


def test_retry_or_fail_retryable_attempt_2():
    """Second attempt should have 30s backoff."""
    with pytest.raises(Retry) as exc_info:
        retry_or_fail(
            job_try=2,
            max_tries=4,
            error=TimeoutError("timed out"),
            job_name="test_job",
        )
    assert exc_info.value.defer_score == 30_000  # milliseconds


@patch("app.core.jobs.retry.log_dead_letter")
def test_retry_or_fail_exhausted_goes_to_dead_letter(mock_dead_letter):
    """Last attempt (job_try == max_tries) should NOT retry, should dead letter."""
    retry_or_fail(
        job_try=4,
        max_tries=4,
        error=ConnectionError("still failing"),
        job_name="test_job",
    )
    mock_dead_letter.assert_called_once_with(
        "test_job", "still failing", 4,
    )


@patch("app.core.jobs.retry.log_dead_letter")
def test_retry_or_fail_non_retryable_skips_retry(mock_dead_letter):
    """Non-retryable error should go directly to dead letter, even on attempt 1."""
    retry_or_fail(
        job_try=1,
        max_tries=4,
        error=ValueError("invalid email"),
        job_name="test_job",
        to="bad@email",
    )
    mock_dead_letter.assert_called_once_with(
        "test_job", "invalid email", 1, to="bad@email",
    )


@patch("app.core.jobs.retry.log_dead_letter")
def test_retry_or_fail_custom_non_retryable_error(mock_dead_letter):
    """NonRetryableJobError should skip retries."""
    retry_or_fail(
        job_try=1,
        max_tries=4,
        error=NonRetryableJobError("permanent failure"),
        job_name="test_job",
    )
    mock_dead_letter.assert_called_once()


@patch("app.core.jobs.retry.log_dead_letter")
def test_retry_or_fail_unknown_error_goes_to_dead_letter(mock_dead_letter):
    """Unknown exception type should NOT be retried (allowlist miss → dead letter)."""
    retry_or_fail(
        job_try=1,
        max_tries=4,
        error=RuntimeError("unknown issue"),
        job_name="test_job",
    )
    mock_dead_letter.assert_called_once()


# ─── log_dead_letter ───


@patch("app.core.jobs.retry.logger")
@patch("app.core.metrics.job_dead_letter_total")
def test_dead_letter_increments_metric_and_logs(mock_counter, mock_logger):
    """Dead letter should increment Prometheus counter and log error."""
    log_dead_letter("my_job", "something failed", 3, tenant="test")

    mock_counter.labels.assert_called_once_with(job_name="my_job")
    mock_counter.labels.return_value.inc.assert_called_once()

    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args
    assert call_kwargs[0][0] == "job.dead_letter"
    assert call_kwargs[1]["job"] == "my_job"
    assert call_kwargs[1]["attempts"] == 3
