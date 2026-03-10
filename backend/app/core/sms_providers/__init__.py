"""SMS provider factory.

Resolves provider name -> concrete SMSProviderBase implementation.
Validates required config at creation time (fail-fast on misconfig).
"""

import structlog

from app.config import settings
from app.core.sms_providers.base import SMSProviderBase

logger = structlog.get_logger()


def create_sms_provider(provider_name: str) -> SMSProviderBase:
    """Create an SMS provider by name. Raises ValueError on unknown/misconfigured provider."""
    name = provider_name.lower().strip()

    if name == "brevo":
        from app.core.sms_providers.brevo import BrevoSMSProvider

        if not settings.brevo_api_key:
            raise ValueError("Brevo SMS provider requires BREVO_API_KEY")
        return BrevoSMSProvider()

    if name == "twilio":
        from app.core.sms_providers.twilio import TwilioProvider

        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise ValueError(
                "Twilio provider requires TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN"
            )
        return TwilioProvider()

    if name == "vonage":
        from app.core.sms_providers.vonage import VonageProvider

        if not settings.vonage_api_key or not settings.vonage_api_secret:
            raise ValueError(
                "Vonage provider requires VONAGE_API_KEY and VONAGE_API_SECRET"
            )
        return VonageProvider()

    raise ValueError(
        f"Unknown SMS provider '{name}'. Supported: brevo, twilio, vonage"
    )
