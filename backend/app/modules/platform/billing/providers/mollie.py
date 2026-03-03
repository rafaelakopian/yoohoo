"""Mollie payment provider implementation.

Uses httpx to communicate with Mollie REST API v2.
Webhook security: fetch-back pattern (Mollie sends only payment ID, we fetch details over HTTPS).
"""

import httpx
import structlog

from app.core.circuit_breaker import get_circuit_breaker
from app.modules.platform.billing.providers.base import (
    CreatePaymentRequest,
    PaymentProviderBase,
    PaymentResult,
    RefundResult,
    WebhookVerificationResult,
)

logger = structlog.get_logger()

# Mollie status → our normalized PaymentStatus
_STATUS_MAP = {
    "open": "pending",
    "pending": "processing",
    "authorized": "processing",
    "paid": "paid",
    "failed": "failed",
    "canceled": "cancelled",
    "expired": "expired",
}


_mollie_breaker = get_circuit_breaker("mollie", failure_threshold=5, recovery_timeout=60.0)


class MollieProvider(PaymentProviderBase):
    """Mollie payment provider using REST API v2."""

    BASE_URL = "https://api.mollie.com/v2"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_payment(self, request: CreatePaymentRequest) -> PaymentResult:
        """Create a payment via Mollie API (circuit-breaker protected)."""
        return await _mollie_breaker.call(self._create_payment_inner, request)

    async def _create_payment_inner(self, request: CreatePaymentRequest) -> PaymentResult:
        payload = {
            "amount": {
                "currency": request.currency,
                "value": f"{request.amount_cents / 100:.2f}",
            },
            "description": request.description,
            "redirectUrl": request.redirect_url,
            "webhookUrl": request.webhook_url,
            "metadata": request.metadata or {},
        }
        if request.payment_method:
            payload["method"] = request.payment_method

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/payments",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return PaymentResult(
            provider_payment_id=data["id"],
            status=self._normalize_status(data["status"]),
            checkout_url=data.get("_links", {}).get("checkout", {}).get("href"),
            payment_method=data.get("method"),
            raw_data={"id": data["id"], "status": data["status"]},
        )

    async def get_payment(self, provider_payment_id: str) -> PaymentResult:
        """Fetch payment status from Mollie (circuit-breaker protected)."""
        return await _mollie_breaker.call(self._get_payment_inner, provider_payment_id)

    async def _get_payment_inner(self, provider_payment_id: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/payments/{provider_payment_id}",
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return PaymentResult(
            provider_payment_id=data["id"],
            status=self._normalize_status(data["status"]),
            payment_method=data.get("method"),
            paid_at=data.get("paidAt"),
            raw_data={"id": data["id"], "status": data["status"]},
        )

    async def create_refund(
        self,
        provider_payment_id: str,
        amount_cents: int | None = None,
        description: str | None = None,
    ) -> RefundResult:
        """Create a refund via Mollie API."""
        payload: dict = {}
        if amount_cents:
            payload["amount"] = {
                "currency": "EUR",
                "value": f"{amount_cents / 100:.2f}",
            }
        if description:
            payload["description"] = description

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/payments/{provider_payment_id}/refunds",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        refund_amount = int(float(data["amount"]["value"]) * 100)
        return RefundResult(
            provider_refund_id=data["id"],
            amount_cents=refund_amount,
            status=data.get("status", "pending"),
            raw_data={"id": data["id"], "status": data.get("status")},
        )

    async def verify_webhook(
        self, request_body: bytes, headers: dict[str, str]
    ) -> WebhookVerificationResult:
        """Mollie webhook verification: extract payment ID for fetch-back.

        Mollie sends only a payment ID. We verify by fetching the payment
        from Mollie's API using our API key.
        """
        body = request_body.decode("utf-8")
        payment_id = None
        for part in body.split("&"):
            if part.startswith("id="):
                payment_id = part[3:]
                break

        if not payment_id:
            return WebhookVerificationResult(is_valid=False)

        # Fetch-back: verify the payment exists by calling Mollie API
        try:
            result = await self.get_payment(payment_id)
            return WebhookVerificationResult(
                is_valid=True,
                event_id=f"mollie_{payment_id}",
                event_type=f"payment.{result.status}",
                payment_id=payment_id,
                payload=result.raw_data,
            )
        except Exception:
            logger.exception("mollie.verify_webhook.fetch_back_failed")
            return WebhookVerificationResult(is_valid=False)

    async def create_checkout_session(
        self, request: CreatePaymentRequest
    ) -> PaymentResult:
        """Create a Mollie Checkout payment (PCI SAQ-A).

        Mollie payments are inherently hosted checkout (SAQ-A compliant).
        """
        return await self.create_payment(request)

    async def list_payment_methods(
        self, customer_id: str | None = None
    ) -> list[dict]:
        """List available Mollie payment methods."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/methods",
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            {
                "id": m["id"],
                "description": m["description"],
                "image": m.get("image", {}).get("svg"),
            }
            for m in data.get("_embedded", {}).get("methods", [])
        ]

    async def cancel_payment(self, provider_payment_id: str) -> PaymentResult:
        """Cancel a pending Mollie payment."""
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.BASE_URL}/payments/{provider_payment_id}",
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return PaymentResult(
            provider_payment_id=data["id"],
            status=self._normalize_status(data["status"]),
            raw_data={"id": data["id"], "status": data["status"]},
        )

    def _normalize_status(self, mollie_status: str) -> str:
        """Map Mollie statuses to our PaymentStatus enum values."""
        return _STATUS_MAP.get(mollie_status, "pending")
