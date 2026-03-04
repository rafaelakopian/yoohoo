"""Brevo (formerly Sendinblue) email provider using REST API.

Uses httpx (already in requirements) — no SDK dependency.
API docs: https://developers.brevo.com/reference/sendtransacemail
"""

import httpx
import structlog

from app.config import settings
from app.core.circuit_breaker import get_circuit_breaker
from app.core.email_providers.base import EmailProviderBase

logger = structlog.get_logger()

_brevo_breaker = get_circuit_breaker(
    "email_brevo", failure_threshold=3, recovery_timeout=60.0, success_threshold=1
)


class BrevoProvider(EmailProviderBase):
    """Brevo email provider via REST API."""

    API_URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "api-key": settings.brevo_api_key,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
        return self._client

    async def send(
        self, to: str, subject: str, html_body: str, from_email: str, from_name: str,
    ) -> bool:
        return await _brevo_breaker.call(
            self._send_inner, to, subject, html_body, from_email, from_name
        )

    async def _send_inner(
        self, to: str, subject: str, html_body: str, from_email: str, from_name: str,
    ) -> bool:
        sender = {"email": from_email}
        if from_name:
            sender["name"] = from_name

        payload = {
            "sender": sender,
            "to": [{"email": to}],
            "subject": subject,
            "htmlContent": html_body,
        }

        client = self._get_client()
        resp = await client.post(self.API_URL, json=payload)
        resp.raise_for_status()

        data = resp.json()
        logger.info(
            "email.sent",
            provider="brevo",
            to=to,
            subject=subject,
            message_id=data.get("messageId"),
        )
        return True

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
