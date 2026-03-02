import html as html_module

import aiosmtplib
import structlog
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.core.circuit_breaker import CircuitOpenError, get_circuit_breaker

logger = structlog.get_logger()


def _sanitize_header(value: str) -> str:
    """Strip newlines from email header values to prevent header injection."""
    return value.replace("\r", "").replace("\n", "")


def escape(value: str) -> str:
    """HTML-escape user-controlled values for safe insertion into email templates."""
    return html_module.escape(str(value), quote=True)

_email_breaker = get_circuit_breaker(
    "email", failure_threshold=3, recovery_timeout=60.0, success_threshold=1
)


async def send_email_safe(to: str, subject: str, html_body: str) -> bool:
    """Send email with circuit breaker protection. Returns False on failure."""
    try:
        return await _email_breaker.call(_send_email_raw, to, subject, html_body)
    except CircuitOpenError:
        logger.warning("email.circuit_open", to=to, subject=subject)
        return False
    except Exception:
        logger.error("email.send_failed_safe", to=to, subject=subject, exc_info=True)
        return False


async def _send_email_raw(to: str, subject: str, html_body: str) -> bool:
    """Raw email send (used inside circuit breaker)."""
    message = MIMEMultipart("alternative")
    message["From"] = settings.smtp_from
    message["To"] = _sanitize_header(to)
    message["Subject"] = _sanitize_header(subject)
    message.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_use_tls,
        start_tls=settings.smtp_use_tls,
    )
    logger.info("email.sent", to=to, subject=subject)
    return True


async def send_email(to: str, subject: str, html_body: str) -> bool:
    message = MIMEMultipart("alternative")
    message["From"] = settings.smtp_from
    message["To"] = _sanitize_header(to)
    message["Subject"] = _sanitize_header(subject)
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_use_tls,
        )
        logger.info("email.sent", to=to, subject=subject)
        return True
    except Exception as e:
        logger.error("email.send_failed", to=to, subject=subject, error=str(e))
        return False


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
