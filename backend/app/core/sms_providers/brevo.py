"""Brevo (formerly Sendinblue) SMS provider using REST API.

Uses httpx (already in requirements) — no SDK dependency.
API docs: https://developers.brevo.com/reference/sendtransacsms
"""

import httpx
import structlog

from app.config import settings
from app.core.circuit_breaker import get_circuit_breaker
from app.core.sms_providers.base import SMSProviderBase, SMSResult

logger = structlog.get_logger()

_brevo_sms_breaker = get_circuit_breaker(
    "sms_brevo", failure_threshold=3, recovery_timeout=60.0, success_threshold=1
)


class BrevoSMSProvider(SMSProviderBase):
    """Brevo SMS provider via REST API."""

    API_URL = "https://api.brevo.com/v3/transactionalSMS/sms"

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

    async def send(self, to: str, message: str, sender: str) -> SMSResult:
        return await _brevo_sms_breaker.call(
            self._send_inner, to, message, sender
        )

    async def _send_inner(self, to: str, message: str, sender: str) -> SMSResult:
        payload = {
            "type": "transactional",
            "unicodeEnabled": True,
            "sender": sender,
            "recipient": to,
            "content": message,
        }

        client = self._get_client()
        resp = await client.post(self.API_URL, json=payload)
        resp.raise_for_status()

        data = resp.json()
        message_id = data.get("messageId") or data.get("reference")

        logger.info(
            "sms.sent",
            provider="brevo",
            to=f"***{to[-4:]}",
            message_id=message_id,
        )
        return SMSResult(success=True, message_id=str(message_id), provider="brevo")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
