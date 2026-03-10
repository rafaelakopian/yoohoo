"""Vonage (formerly Nexmo) SMS provider using REST API.

Uses httpx (already in requirements) — no SDK dependency.
API docs: https://developer.vonage.com/en/messaging/sms/overview
"""

import httpx
import structlog

from app.config import settings
from app.core.circuit_breaker import get_circuit_breaker
from app.core.sms_providers.base import SMSProviderBase, SMSResult

logger = structlog.get_logger()

_vonage_breaker = get_circuit_breaker(
    "sms_vonage", failure_threshold=3, recovery_timeout=60.0, success_threshold=1
)


class VonageProvider(SMSProviderBase):
    """Vonage SMS provider via REST API (no SDK needed)."""

    API_URL = "https://rest.nexmo.com/sms/json"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
        return self._client

    async def send(self, to: str, message: str, sender: str) -> SMSResult:
        return await _vonage_breaker.call(
            self._send_inner, to, message, sender
        )

    async def _send_inner(self, to: str, message: str, sender: str) -> SMSResult:
        payload = {
            "api_key": settings.vonage_api_key,
            "api_secret": settings.vonage_api_secret,
            "from": sender,
            "to": to.lstrip("+"),
            "text": message,
            "type": "unicode",
        }

        client = self._get_client()
        resp = await client.post(self.API_URL, json=payload)
        resp.raise_for_status()

        data = resp.json()
        messages = data.get("messages", [{}])
        first = messages[0] if messages else {}
        status = first.get("status", "1")
        message_id = first.get("message-id")

        if status != "0":
            error_text = first.get("error-text", "Unknown error")
            logger.warning(
                "sms.failed",
                provider="vonage",
                to=f"***{to[-4:]}",
                error=error_text,
            )
            return SMSResult(success=False, provider="vonage", error=error_text)

        logger.info(
            "sms.sent",
            provider="vonage",
            to=f"***{to[-4:]}",
            message_id=message_id,
        )
        return SMSResult(success=True, message_id=message_id, provider="vonage")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
