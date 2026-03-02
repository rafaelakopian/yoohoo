"""Stripe payment provider implementation.

Uses the Stripe Python SDK.
Webhook security: HMAC-SHA256 verification via stripe-signature header.
"""

import stripe
import structlog

from app.core.circuit_breaker import CircuitOpenError, get_circuit_breaker
from app.modules.platform.billing.providers.base import (
    CreatePaymentRequest,
    PaymentProviderBase,
    PaymentResult,
    RefundResult,
    WebhookVerificationResult,
)

logger = structlog.get_logger()

# Stripe PaymentIntent status → our normalized PaymentStatus
_STATUS_MAP = {
    "requires_payment_method": "pending",
    "requires_confirmation": "pending",
    "requires_action": "pending",
    "processing": "processing",
    "requires_capture": "processing",
    "succeeded": "paid",
    "canceled": "cancelled",
}


_stripe_breaker = get_circuit_breaker("stripe", failure_threshold=5, recovery_timeout=60.0)


class StripeProvider(PaymentProviderBase):
    """Stripe payment provider using Stripe SDK."""

    def _client(self) -> stripe.StripeClient:
        """Get a configured Stripe client."""
        return stripe.StripeClient(self.api_key)

    async def create_payment(self, request: CreatePaymentRequest) -> PaymentResult:
        """Create a Stripe PaymentIntent (circuit-breaker protected)."""
        return await _stripe_breaker.call(self._create_payment_inner, request)

    async def _create_payment_inner(self, request: CreatePaymentRequest) -> PaymentResult:
        client = self._client()
        intent = client.payment_intents.create(
            params={
                "amount": request.amount_cents,
                "currency": request.currency.lower(),
                "description": request.description,
                "metadata": request.metadata or {},
                "payment_method_types": (
                    [request.payment_method] if request.payment_method else ["card", "ideal"]
                ),
            },
            options={"idempotency_key": request.idempotency_key} if request.idempotency_key else {},
        )

        return PaymentResult(
            provider_payment_id=intent.id,
            status=self._normalize_status(intent.status),
            checkout_url=None,  # PaymentIntents don't have checkout URLs
            raw_data={"id": intent.id, "status": intent.status},
        )

    async def get_payment(self, provider_payment_id: str) -> PaymentResult:
        """Fetch payment status from Stripe (circuit-breaker protected)."""
        return await _stripe_breaker.call(self._get_payment_inner, provider_payment_id)

    async def _get_payment_inner(self, provider_payment_id: str) -> PaymentResult:
        client = self._client()
        intent = client.payment_intents.retrieve(provider_payment_id)

        return PaymentResult(
            provider_payment_id=intent.id,
            status=self._normalize_status(intent.status),
            payment_method=str(intent.payment_method) if intent.payment_method else None,
            raw_data={"id": intent.id, "status": intent.status},
        )

    async def create_refund(
        self,
        provider_payment_id: str,
        amount_cents: int | None = None,
        description: str | None = None,
    ) -> RefundResult:
        """Create a refund via Stripe API."""
        client = self._client()
        params: dict = {"payment_intent": provider_payment_id}
        if amount_cents:
            params["amount"] = amount_cents
        if description:
            params["reason"] = "requested_by_customer"

        refund = client.refunds.create(params=params)

        return RefundResult(
            provider_refund_id=refund.id,
            amount_cents=refund.amount,
            status=refund.status,
            raw_data={"id": refund.id, "status": refund.status},
        )

    async def verify_webhook(
        self, request_body: bytes, headers: dict[str, str]
    ) -> WebhookVerificationResult:
        """Verify Stripe webhook via HMAC-SHA256 signature."""
        sig_header = headers.get("stripe-signature", "")
        if not sig_header or not self.webhook_secret:
            return WebhookVerificationResult(is_valid=False)

        try:
            event = stripe.Webhook.construct_event(
                request_body, sig_header, self.webhook_secret
            )
            data_obj = event.get("data", {}).get("object", {})
            payment_id = data_obj.get("id")

            return WebhookVerificationResult(
                is_valid=True,
                event_id=event["id"],
                event_type=event["type"],
                payment_id=payment_id,
                payload={"type": event["type"]},
            )
        except stripe.SignatureVerificationError:
            logger.warning("stripe.webhook.signature_invalid")
            return WebhookVerificationResult(is_valid=False)
        except Exception:
            logger.exception("stripe.webhook.verification_error")
            return WebhookVerificationResult(is_valid=False)

    async def create_checkout_session(
        self, request: CreatePaymentRequest
    ) -> PaymentResult:
        """Create a Stripe Checkout Session (PCI SAQ-A)."""
        client = self._client()
        session = client.checkout.sessions.create(
            params={
                "payment_method_types": (
                    [request.payment_method] if request.payment_method else ["card", "ideal"]
                ),
                "line_items": [
                    {
                        "price_data": {
                            "currency": request.currency.lower(),
                            "unit_amount": request.amount_cents,
                            "product_data": {"name": request.description},
                        },
                        "quantity": 1,
                    }
                ],
                "mode": "payment",
                "success_url": request.redirect_url,
                "cancel_url": request.redirect_url,
                "customer_email": request.customer_email,
                "metadata": request.metadata or {},
            }
        )

        return PaymentResult(
            provider_payment_id=session.payment_intent or session.id,
            status="pending",
            checkout_url=session.url,
            raw_data={"session_id": session.id, "payment_intent": session.payment_intent},
        )

    async def list_payment_methods(
        self, customer_id: str | None = None
    ) -> list[dict]:
        """List Stripe payment methods for a customer."""
        if not customer_id:
            return []

        client = self._client()
        methods = client.payment_methods.list(
            params={"customer": customer_id, "type": "card"}
        )

        return [
            {
                "id": m.id,
                "type": m.type,
                "last4": m.card.last4 if m.card else None,
                "brand": m.card.brand if m.card else None,
                "exp_month": m.card.exp_month if m.card else None,
                "exp_year": m.card.exp_year if m.card else None,
            }
            for m in methods.data
        ]

    async def cancel_payment(self, provider_payment_id: str) -> PaymentResult:
        """Cancel a Stripe PaymentIntent."""
        client = self._client()
        intent = client.payment_intents.cancel(provider_payment_id)

        return PaymentResult(
            provider_payment_id=intent.id,
            status=self._normalize_status(intent.status),
            raw_data={"id": intent.id, "status": intent.status},
        )

    def _normalize_status(self, stripe_status: str) -> str:
        """Map Stripe statuses to our PaymentStatus enum values."""
        return _STATUS_MAP.get(stripe_status, "pending")
