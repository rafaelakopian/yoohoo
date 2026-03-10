"""SMS sending with multi-provider support and automatic fallback.

Public API:
    send_sms(to, message, *, sender) -> bool         # primary only, never raises
    send_sms_safe(to, message, *, sender) -> bool     # primary + fallback, never raises
    is_sms_configured() -> bool                       # check if SMS is available
"""

import structlog

from app.config import settings
from app.core.circuit_breaker import CircuitOpenError
from app.core.sms_providers import create_sms_provider
from app.core.sms_providers.base import SMSProviderBase

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Provider lifecycle (lazy init)
# ---------------------------------------------------------------------------
_primary: SMSProviderBase | None = None
_fallback: SMSProviderBase | None = None
_initialized: bool = False


def is_sms_configured() -> bool:
    """Check if an SMS provider is configured (without initializing)."""
    return bool(settings.sms_provider)


def _get_providers() -> tuple[SMSProviderBase | None, SMSProviderBase | None]:
    """Lazy-init SMS providers from config. Returns (None, None) if not configured."""
    global _primary, _fallback, _initialized  # noqa: PLW0603

    if _initialized:
        return _primary, _fallback

    if not settings.sms_provider:
        _initialized = True
        return None, None

    _primary = create_sms_provider(settings.sms_provider)
    logger.info("sms.provider_initialized", provider=settings.sms_provider)

    if settings.sms_fallback_provider:
        fb = settings.sms_fallback_provider.lower().strip()
        if fb == settings.sms_provider.lower().strip():
            raise ValueError(
                f"SMS_FALLBACK_PROVIDER cannot be the same as SMS_PROVIDER ('{fb}')"
            )
        _fallback = create_sms_provider(fb)
        logger.info("sms.fallback_initialized", provider=fb)

    _initialized = True
    return _primary, _fallback


async def close_providers() -> None:
    """Shut down SMS provider HTTP clients. Called at app/worker shutdown."""
    global _primary, _fallback, _initialized  # noqa: PLW0603

    if _primary:
        await _primary.close()
    if _fallback:
        await _fallback.close()
    _primary = None
    _fallback = None
    _initialized = False


# ---------------------------------------------------------------------------
# Send functions
# ---------------------------------------------------------------------------

async def send_sms_safe(
    to: str,
    message: str,
    *,
    sender: str | None = None,
) -> bool:
    """Send SMS with circuit breaker + automatic fallback. Never raises."""
    primary, fallback = _get_providers()

    if primary is None:
        logger.warning("sms.not_configured", to=f"***{to[-4:]}")
        return False

    sms_sender = sender or settings.sms_sender_name
    log_ctx = {"to": f"***{to[-4:]}", "sender": sms_sender}

    # Try primary
    try:
        result = await primary.send(to, message, sms_sender)
        return result.success
    except CircuitOpenError:
        logger.warning("sms.primary_circuit_open", provider=settings.sms_provider, **log_ctx)
    except Exception:
        logger.warning("sms.primary_failed", provider=settings.sms_provider, **log_ctx, exc_info=True)

    # Try fallback
    if fallback is None:
        logger.warning("sms.send_failed_no_fallback", **log_ctx)
        return False

    try:
        result = await fallback.send(to, message, sms_sender)
        logger.info("sms.fallback_succeeded", provider=settings.sms_fallback_provider, **log_ctx)
        return result.success
    except Exception:
        logger.error("sms.fallback_failed", provider=settings.sms_fallback_provider, **log_ctx, exc_info=True)
        return False


async def send_sms(
    to: str,
    message: str,
    *,
    sender: str | None = None,
) -> bool:
    """Send SMS via primary provider only (no fallback). Returns False on failure."""
    primary, _ = _get_providers()

    if primary is None:
        logger.warning("sms.not_configured", to=f"***{to[-4:]}")
        return False

    sms_sender = sender or settings.sms_sender_name

    try:
        result = await primary.send(to, message, sms_sender)
        return result.success
    except Exception as e:
        logger.error(
            "sms.send_failed",
            to=f"***{to[-4:]}",
            sender=sms_sender,
            error=str(e),
        )
        return False
