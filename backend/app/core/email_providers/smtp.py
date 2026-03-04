"""SMTP email provider using aiosmtplib.

TLS modes:
- SMTP_USE_TLS=true + port 465: implicit TLS (use_tls=True)
- SMTP_USE_TLS=true + other port: STARTTLS (start_tls=True)
- SMTP_USE_TLS=false: no TLS (dev/mailpit)
"""

import aiosmtplib
import structlog
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.core.circuit_breaker import get_circuit_breaker
from app.core.email_providers.base import EmailProviderBase

logger = structlog.get_logger()

_smtp_breaker = get_circuit_breaker(
    "email_smtp", failure_threshold=3, recovery_timeout=60.0, success_threshold=1
)


def _resolve_tls() -> tuple[bool, bool, str]:
    """Determine TLS flags from config. Returns (use_tls, start_tls, mode_label)."""
    if not settings.smtp_use_tls:
        return False, False, "none"
    if settings.smtp_port == 465:
        return True, False, "implicit"
    return False, True, "starttls"


class SmtpProvider(EmailProviderBase):
    """SMTP email provider."""

    def __init__(self) -> None:
        use_tls, start_tls, mode = _resolve_tls()
        self._use_tls = use_tls
        self._start_tls = start_tls
        logger.info(
            "email.smtp.tls_resolved",
            tls_mode=mode,
            port=settings.smtp_port,
            host=settings.smtp_host,
        )

    async def send(
        self, to: str, subject: str, html_body: str, from_email: str, from_name: str,
    ) -> bool:
        return await _smtp_breaker.call(
            self._send_inner, to, subject, html_body, from_email, from_name
        )

    async def _send_inner(
        self, to: str, subject: str, html_body: str, from_email: str, from_name: str,
    ) -> bool:
        message = MIMEMultipart("alternative")
        message["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=self._use_tls,
            start_tls=self._start_tls,
            timeout=30,
        )
        logger.info("email.sent", provider="smtp", to=to, subject=subject)
        return True

    async def close(self) -> None:
        pass
