"""Tests for Stripe HMAC-SHA256 webhook signature verification."""

import hashlib
import hmac
import time
from unittest.mock import patch

from app.modules.platform.billing.webhooks.verification import verify_stripe_signature


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_stripe_header(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a valid Stripe-Signature header for testing."""
    ts = timestamp or int(time.time())
    signed_payload = f"{ts}.".encode() + payload
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


SECRET = "whsec_test_secret_key"
PAYLOAD = b'{"type":"payment_intent.succeeded","data":{}}'


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_stripe_valid_signature():
    header = _build_stripe_header(PAYLOAD, SECRET)
    assert verify_stripe_signature(PAYLOAD, header, SECRET) == {"verified": True}


def test_stripe_custom_tolerance():
    """400s-old timestamp accepted when tolerance=600."""
    ts = int(time.time()) - 400
    header = _build_stripe_header(PAYLOAD, SECRET, timestamp=ts)
    assert verify_stripe_signature(PAYLOAD, header, SECRET, tolerance=600) == {"verified": True}


def test_stripe_empty_payload():
    """Empty payload still produces a valid HMAC."""
    empty = b""
    header = _build_stripe_header(empty, SECRET)
    assert verify_stripe_signature(empty, header, SECRET) == {"verified": True}


# ---------------------------------------------------------------------------
# Missing / malformed header parts
# ---------------------------------------------------------------------------

def test_stripe_missing_timestamp():
    sig = hmac.new(SECRET.encode(), PAYLOAD, hashlib.sha256).hexdigest()
    assert verify_stripe_signature(PAYLOAD, f"v1={sig}", SECRET) is None


def test_stripe_missing_v1():
    assert verify_stripe_signature(PAYLOAD, f"t={int(time.time())}", SECRET) is None


def test_stripe_empty_header():
    assert verify_stripe_signature(PAYLOAD, "", SECRET) is None


def test_stripe_malformed_header():
    assert verify_stripe_signature(PAYLOAD, "garbage-no-equals", SECRET) is None


# ---------------------------------------------------------------------------
# Timestamp tolerance
# ---------------------------------------------------------------------------

def test_stripe_timestamp_too_old():
    ts = int(time.time()) - 600  # 10 min ago, tolerance=300s
    header = _build_stripe_header(PAYLOAD, SECRET, timestamp=ts)
    assert verify_stripe_signature(PAYLOAD, header, SECRET) is None


def test_stripe_timestamp_future():
    ts = int(time.time()) + 600  # 10 min in future
    header = _build_stripe_header(PAYLOAD, SECRET, timestamp=ts)
    assert verify_stripe_signature(PAYLOAD, header, SECRET) is None


# ---------------------------------------------------------------------------
# Signature mismatch
# ---------------------------------------------------------------------------

def test_stripe_wrong_signature():
    """Tampered payload doesn't match original signature."""
    header = _build_stripe_header(PAYLOAD, SECRET)
    assert verify_stripe_signature(b'{"type":"charge.refunded"}', header, SECRET) is None


def test_stripe_wrong_secret():
    """Different secret produces different HMAC."""
    header = _build_stripe_header(PAYLOAD, SECRET)
    assert verify_stripe_signature(PAYLOAD, header, "wrong_secret") is None


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------

def test_stripe_exception_returns_none():
    """Internal exception gracefully returns None."""
    header = _build_stripe_header(PAYLOAD, SECRET)
    with patch(
        "app.modules.platform.billing.webhooks.verification.time.time",
        side_effect=Exception("boom"),
    ):
        assert verify_stripe_signature(PAYLOAD, header, SECRET) is None
