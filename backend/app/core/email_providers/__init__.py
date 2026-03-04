"""Email provider factory.

Resolves provider name → concrete EmailProviderBase implementation.
Validates required config at creation time (fail-fast on misconfig).
"""

import structlog

from app.config import settings
from app.core.email_providers.base import EmailProviderBase

logger = structlog.get_logger()


def create_email_provider(provider_name: str) -> EmailProviderBase:
    """Create an email provider by name. Raises ValueError on unknown/misconfigured provider."""
    name = provider_name.lower().strip()

    if name == "smtp":
        from app.core.email_providers.smtp import SmtpProvider

        if not settings.smtp_host:
            raise ValueError("SMTP provider requires SMTP_HOST")
        return SmtpProvider()

    if name == "resend":
        from app.core.email_providers.resend import ResendProvider

        if not settings.resend_api_key:
            raise ValueError("Resend provider requires RESEND_API_KEY")
        return ResendProvider()

    if name == "brevo":
        from app.core.email_providers.brevo import BrevoProvider

        if not settings.brevo_api_key:
            raise ValueError("Brevo provider requires BREVO_API_KEY")
        return BrevoProvider()

    raise ValueError(
        f"Unknown email provider '{name}'. Supported: smtp, resend, brevo"
    )
