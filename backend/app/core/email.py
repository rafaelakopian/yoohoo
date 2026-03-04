"""Email sending with multi-provider support and automatic fallback.

Public API:
    EmailSender                                        # enum for sender categories
    send_email_safe(to, subject, html_body, *, sender) -> bool   # primary + fallback, never raises
    send_email(to, subject, html_body, *, sender) -> bool        # primary only, never raises
    escape(value) -> str                                          # HTML-escape for templates
    build_verification_email(name, token) -> (subject, html)
"""

import html as html_module
from enum import Enum

import structlog

from app.config import settings
from app.core.circuit_breaker import CircuitOpenError
from app.core.email_providers import create_email_provider
from app.core.email_providers.base import EmailProviderBase

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Sender categories
# ---------------------------------------------------------------------------

class EmailSender(str, Enum):
    """Email sender category — determines from address and display name."""
    ACCOUNT = "account"
    SECURITY = "security"
    NOTIFICATION = "notification"
    BILLING = "billing"
    GENERAL = "general"


# Maps sender type to (from_attr, name_attr) on settings.
_SENDER_CONFIG: dict[EmailSender, tuple[str, str]] = {
    EmailSender.ACCOUNT: ("email_account_from", "email_account_name"),
    EmailSender.SECURITY: ("email_security_from", "email_security_name"),
    EmailSender.NOTIFICATION: ("email_notification_from", "email_notification_name"),
    EmailSender.BILLING: ("email_billing_from", "email_billing_name"),
}


def _resolve_sender(sender: EmailSender | None) -> tuple[str, str]:
    """Return (from_email, from_name) for the given sender type.

    Falls back to smtp_from / email_from_name when per-type config is empty.
    None and GENERAL both resolve to the default sender.
    """
    # None / GENERAL → default sender
    if sender is None or sender == EmailSender.GENERAL:
        return settings.smtp_from, settings.email_from_name

    if sender in _SENDER_CONFIG:
        from_attr, name_attr = _SENDER_CONFIG[sender]
        from_email = getattr(settings, from_attr) or settings.smtp_from
        from_name = getattr(settings, name_attr) or settings.email_from_name
        return from_email, from_name

    return settings.smtp_from, settings.email_from_name


# ---------------------------------------------------------------------------
# Provider lifecycle (lazy init)
# ---------------------------------------------------------------------------
_primary: EmailProviderBase | None = None
_fallback: EmailProviderBase | None = None
_initialized: bool = False


def _get_providers() -> tuple[EmailProviderBase, EmailProviderBase | None]:
    """Lazy-init providers from config. Raises ValueError on misconfig."""
    global _primary, _fallback, _initialized  # noqa: PLW0603

    if _initialized:
        assert _primary is not None
        return _primary, _fallback

    _primary = create_email_provider(settings.email_provider)
    logger.info("email.provider_initialized", provider=settings.email_provider)

    if settings.email_fallback_provider:
        fb = settings.email_fallback_provider.lower().strip()
        if fb == settings.email_provider.lower().strip():
            raise ValueError(
                f"EMAIL_FALLBACK_PROVIDER cannot be the same as EMAIL_PROVIDER ('{fb}')"
            )
        _fallback = create_email_provider(fb)
        logger.info("email.fallback_initialized", provider=fb)

    # Log resolved senders at startup for production visibility
    for sender_type in EmailSender:
        from_email, from_name = _resolve_sender(sender_type)
        logger.info(
            "email.sender_configured",
            type=sender_type.value,
            from_email=from_email,
            from_name=from_name,
        )

    _initialized = True
    return _primary, _fallback


async def close_providers() -> None:
    """Shut down provider HTTP clients. Called at app/worker shutdown."""
    global _primary, _fallback, _initialized  # noqa: PLW0603

    if _primary:
        await _primary.close()
    if _fallback:
        await _fallback.close()
    _primary = None
    _fallback = None
    _initialized = False


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _sanitize_header(value: str) -> str:
    """Strip newlines from email header values to prevent header injection."""
    return value.replace("\r", "").replace("\n", "")


def escape(value: str) -> str:
    """HTML-escape user-controlled values for safe insertion into email templates."""
    return html_module.escape(str(value), quote=True)


# ---------------------------------------------------------------------------
# Send functions
# ---------------------------------------------------------------------------

async def send_email_safe(
    to: str,
    subject: str,
    html_body: str,
    *,
    sender: EmailSender | None = None,
) -> bool:
    """Send email with circuit breaker + automatic fallback. Never raises."""
    primary, fallback = _get_providers()
    safe_to = _sanitize_header(to)
    safe_subject = _sanitize_header(subject)
    from_email, from_name = _resolve_sender(sender)

    log_ctx = {
        "to": safe_to,
        "subject": safe_subject,
        "sender": sender.value if sender else "general",
        "from_email": from_email,
    }

    # Try primary
    try:
        return await primary.send(
            safe_to, safe_subject, html_body,
            from_email, from_name,
        )
    except CircuitOpenError:
        logger.warning("email.primary_circuit_open", provider=settings.email_provider, **log_ctx)
    except Exception:
        logger.warning("email.primary_failed", provider=settings.email_provider, **log_ctx, exc_info=True)

    # Try fallback
    if fallback is None:
        logger.warning("email.send_failed_no_fallback", **log_ctx)
        return False

    try:
        result = await fallback.send(
            safe_to, safe_subject, html_body,
            from_email, from_name,
        )
        logger.info("email.fallback_succeeded", provider=settings.email_fallback_provider, **log_ctx)
        return result
    except Exception:
        logger.error("email.fallback_failed", provider=settings.email_fallback_provider, **log_ctx, exc_info=True)
        return False


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    *,
    sender: EmailSender | None = None,
) -> bool:
    """Send email via primary provider only (no fallback). Returns False on failure."""
    primary, _ = _get_providers()
    safe_to = _sanitize_header(to)
    safe_subject = _sanitize_header(subject)
    from_email, from_name = _resolve_sender(sender)

    try:
        await primary.send(
            safe_to, safe_subject, html_body,
            from_email, from_name,
        )
        return True
    except Exception as e:
        logger.error(
            "email.send_failed",
            to=safe_to,
            subject=safe_subject,
            sender=sender.value if sender else "general",
            from_email=from_email,
            error=str(e),
        )
        return False


# ---------------------------------------------------------------------------
# Email builders
# ---------------------------------------------------------------------------

def build_verification_email(full_name: str, token: str) -> tuple[str, str]:
    from app.modules.tenant.notification.templates import _base_template

    verify_url = f"{settings.frontend_url}/auth/verify-email?token={token}"
    subject = f"Bevestig je e-mailadres — {settings.platform_name}"
    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 24px;">
      Bedankt voor je registratie! Klik op de knop hieronder om je e-mailadres te bevestigen.
    </p>
    <table cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
      <tr><td align="center" style="background-color:#cd095b;border-radius:8px;">
        <a href="{verify_url}" style="display:inline-block;padding:14px 32px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:bold;">
          E-mailadres bevestigen
        </a>
      </td></tr>
    </table>
    <p style="color:#767a81;font-size:13px;line-height:1.5;margin:0 0 8px;">
      Of kopieer deze link in je browser:
    </p>
    <p style="color:#066aab;font-size:13px;word-break:break-all;margin:0 0 24px;">
      {verify_url}
    </p>
    <p style="color:#979da8;font-size:12px;margin:0;">
      Deze link is {settings.email_verification_expire_hours} uur geldig.
      Als je je niet hebt geregistreerd, kun je deze e-mail negeren.
    </p>"""
    return subject, _base_template("E-mail verificatie", body)
