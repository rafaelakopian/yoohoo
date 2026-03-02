"""Webhook verification for Stripe (HMAC-SHA256) and Mollie (fetch-back)."""

import hashlib
import hmac
import time

import structlog

logger = structlog.get_logger()


def verify_stripe_signature(
    payload: bytes, sig_header: str, webhook_secret: str, tolerance: int = 300
) -> dict | None:
    """Verify Stripe webhook signature (HMAC-SHA256).

    Returns parsed event dict on success, None on failure.
    Tolerance: reject events older than 5 minutes (300s).
    """
    try:
        # Parse the Stripe-Signature header: t=timestamp,v1=signature
        elements = dict(
            item.split("=", 1) for item in sig_header.split(",") if "=" in item
        )
        timestamp = elements.get("t")
        signature = elements.get("v1")

        if not timestamp or not signature:
            logger.warning("stripe.webhook.missing_signature_parts")
            return None

        # Check timestamp tolerance
        ts = int(timestamp)
        if abs(time.time() - ts) > tolerance:
            logger.warning("stripe.webhook.timestamp_too_old", age_seconds=abs(time.time() - ts))
            return None

        # Compute expected signature
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            webhook_secret.encode(), signed_payload, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("stripe.webhook.signature_mismatch")
            return None

        return {"verified": True}

    except Exception:
        logger.exception("stripe.webhook.verification_error")
        return None


def extract_mollie_payment_id(payload: bytes) -> str | None:
    """Extract payment ID from Mollie webhook payload.

    Mollie sends a simple form-encoded body: id=tr_xxx.
    Verification is done by fetch-back (calling Mollie API with our key).
    """
    try:
        body = payload.decode("utf-8")
        for part in body.split("&"):
            if part.startswith("id="):
                return part[3:]
        return None
    except Exception:
        logger.exception("mollie.webhook.parse_error")
        return None
