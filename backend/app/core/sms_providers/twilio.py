"""Twilio SMS provider using REST API.

Uses httpx (already in requirements) — no SDK dependency.
API docs: https://www.twilio.com/docs/sms/api/message-resource
"""

import base64

import httpx
import structlog

from app.config import settings
from app.core.circuit_breaker import get_circuit_breaker
from app.core.sms_providers.base import SMSProviderBase, SMSResult

logger = structlog.get_logger()

_twilio_breaker = get_circuit_breaker(
    "sms_twilio", failure_threshold=3, recovery_timeout=60.0, success_threshold=1
)


class TwilioProvider(SMSProviderBase):
    """Twilio SMS provider via REST API (no SDK needed)."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @staticmethod
    def _api_url() -> str:
        return f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            credentials = f"{settings.twilio_account_sid}:{settings.twilio_auth_token}"
            b64 = base64.b64encode(credentials.encode()).decode()
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Basic {b64}"},
                timeout=10,
            )
        return self._client

    async def send(self, to: str, message: str, sender: str) -> SMSResult:
        return await _twilio_breaker.call(
            self._send_inner, to, message, sender
        )

    async def _send_inner(self, to: str, message: str, sender: str) -> SMSResult:
        payload = {
            "To": to,
            "From": sender,
            "Body": message,
        }

        client = self._get_client()
        resp = await client.post(self._api_url(), data=payload)
        resp.raise_for_status()

        data = resp.json()
        message_id = data.get("sid")

        logger.info(
            "sms.sent",
            provider="twilio",
            to=f"***{to[-4:]}",
            message_id=message_id,
        )
        return SMSResult(success=True, message_id=message_id, provider="twilio")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
