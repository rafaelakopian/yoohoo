"""Webhook endpoints for Mollie and Stripe. Public, rate limited, idempotent."""

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.billing.encryption import decrypt_api_key
from app.modules.platform.billing.models import PaymentProvider
from app.modules.platform.billing.providers import PaymentProviderFactory
from app.modules.platform.billing.webhooks.handler import WebhookHandler
from app.modules.platform.billing.webhooks.verification import (
    extract_mollie_payment_id,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/mollie",
    status_code=200,
    dependencies=[Depends(rate_limit(100, 60))],
)
async def mollie_webhook(
    request: Request,
    db: AsyncSession = Depends(get_central_db),
):
    """Mollie webhook endpoint.

    Security: Mollie sends only a payment ID. We verify by fetching the payment
    status from Mollie's API using our API key (fetch-back pattern).
    """
    body = await request.body()
    payment_id = extract_mollie_payment_id(body)

    if not payment_id:
        logger.warning("mollie.webhook.no_payment_id")
        return Response(status_code=200)

    handler = WebhookHandler(db)

    try:
        await handler.process_event(
            provider_type="mollie",
            event_id=f"mollie_{payment_id}",
            event_type="payment.status_changed",
            payment_id=payment_id,
            payload={"id": payment_id},
        )
        await db.commit()
    except Exception:
        logger.exception("mollie.webhook.error", payment_id=payment_id)
        # Always return 200 to prevent Mollie from retrying excessively

    return Response(status_code=200)


@router.post(
    "/stripe",
    status_code=200,
    dependencies=[Depends(rate_limit(100, 60))],
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_central_db),
):
    """Stripe webhook endpoint.

    Security: HMAC-SHA256 verification via stripe-signature header.
    Events older than 5 minutes are rejected by the Stripe SDK.
    Unverified events are rejected with 400.
    """
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not sig_header:
        logger.warning("stripe.webhook.missing_signature")
        return Response(status_code=400)

    # Find all Stripe providers to try their webhook secrets
    result = await db.execute(
        select(PaymentProvider).where(
            PaymentProvider.provider_type == "stripe",
            PaymentProvider.is_active.is_(True),
        )
    )
    providers = result.scalars().all()

    # Try each provider's webhook secret until one verifies
    verified = None
    for provider_config in providers:
        if not provider_config.encrypted_webhook_secret:
            continue

        webhook_secret = decrypt_api_key(provider_config.encrypted_webhook_secret)
        stripe_provider = PaymentProviderFactory.create(
            "stripe",
            api_key=decrypt_api_key(provider_config.encrypted_api_key),
            webhook_secret=webhook_secret,
        )

        verification = await stripe_provider.verify_webhook(
            body, dict(request.headers)
        )
        if verification.is_valid:
            verified = verification
            break

    if not verified:
        logger.warning("stripe.webhook.signature_invalid")
        return Response(status_code=400)

    handler = WebhookHandler(db)

    try:
        normalized_type = _normalize_stripe_event(verified.event_type or "unknown")

        await handler.process_event(
            provider_type="stripe",
            event_id=verified.event_id or f"stripe_{verified.payment_id}",
            event_type=normalized_type,
            payment_id=verified.payment_id,
            payload=verified.payload,
        )
        await db.commit()
    except Exception:
        logger.exception(
            "stripe.webhook.error", event_id=verified.event_id
        )

    return Response(status_code=200)


def _normalize_stripe_event(stripe_type: str) -> str:
    """Map Stripe event types to our normalized event types."""
    mapping = {
        "payment_intent.succeeded": "payment.paid",
        "payment_intent.payment_failed": "payment.failed",
        "payment_intent.canceled": "payment.cancelled",
        "payment_intent.processing": "payment.processing",
        "payment_intent.created": "payment.pending",
        "charge.refunded": "payment.refunded",
        "checkout.session.completed": "payment.paid",
    }
    return mapping.get(stripe_type, f"stripe.{stripe_type}")
