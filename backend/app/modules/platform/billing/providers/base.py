"""Abstract base class for payment provider implementations.

All providers (Mollie, Stripe) implement this interface.
PCI SAQ-A compliant: uses hosted checkout pages, card data never touches our servers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from app.config import settings


def _validate_redirect_url(url: str) -> None:
    """Validate redirect URL against allowed domains to prevent open redirect."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid redirect URL: missing scheme or host")

    # Build allowlist from frontend URL and CORS origins
    allowed_hosts: set[str] = set()
    frontend_parsed = urlparse(settings.frontend_url)
    if frontend_parsed.netloc:
        allowed_hosts.add(frontend_parsed.netloc.split(":")[0])
    for origin in settings.cors_origins_list:
        origin_parsed = urlparse(origin)
        if origin_parsed.netloc:
            allowed_hosts.add(origin_parsed.netloc.split(":")[0])

    redirect_host = parsed.netloc.split(":")[0]
    if redirect_host not in allowed_hosts:
        raise ValueError(
            f"Redirect URL host '{redirect_host}' not in allowed domains"
        )


@dataclass
class CreatePaymentRequest:
    """Unified request to create a payment across providers."""

    amount_cents: int
    currency: str
    description: str
    redirect_url: str
    webhook_url: str
    idempotency_key: Optional[str] = None
    payment_method: Optional[str] = None  # "ideal", "sepa_debit", "creditcard"
    metadata: Optional[dict] = field(default_factory=dict)
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_redirect_url(self.redirect_url)


@dataclass
class PaymentResult:
    """Unified payment result from any provider."""

    provider_payment_id: str
    status: str  # Normalized to our PaymentStatus enum values
    checkout_url: Optional[str] = None
    payment_method: Optional[str] = None
    paid_at: Optional[str] = None
    failure_reason: Optional[str] = None
    raw_data: Optional[dict] = None  # Provider-specific data (redacted, no PCI data)


@dataclass
class RefundResult:
    """Unified refund result."""

    provider_refund_id: str
    amount_cents: int
    status: str
    raw_data: Optional[dict] = None


@dataclass
class WebhookVerificationResult:
    """Result of webhook signature/origin verification."""

    is_valid: bool
    event_id: Optional[str] = None
    event_type: Optional[str] = None
    payment_id: Optional[str] = None
    payload: Optional[dict] = None


class PaymentProviderBase(ABC):
    """Abstract base class for payment provider implementations."""

    def __init__(
        self,
        api_key: str,
        api_secret: str | None = None,
        webhook_secret: str | None = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.webhook_secret = webhook_secret

    @abstractmethod
    async def create_payment(self, request: CreatePaymentRequest) -> PaymentResult:
        """Create a payment and return a checkout URL (PCI SAQ-A)."""
        ...

    @abstractmethod
    async def get_payment(self, provider_payment_id: str) -> PaymentResult:
        """Fetch the current status of a payment."""
        ...

    @abstractmethod
    async def create_refund(
        self,
        provider_payment_id: str,
        amount_cents: int | None = None,
        description: str | None = None,
    ) -> RefundResult:
        """Create a (partial) refund."""
        ...

    @abstractmethod
    async def verify_webhook(
        self, request_body: bytes, headers: dict[str, str]
    ) -> WebhookVerificationResult:
        """Verify and parse a webhook event."""
        ...

    @abstractmethod
    async def create_checkout_session(
        self, request: CreatePaymentRequest
    ) -> PaymentResult:
        """Create a hosted checkout session (PCI SAQ-A compliant)."""
        ...

    @abstractmethod
    async def list_payment_methods(
        self, customer_id: str | None = None
    ) -> list[dict]:
        """List available or stored payment methods."""
        ...

    @abstractmethod
    async def cancel_payment(self, provider_payment_id: str) -> PaymentResult:
        """Cancel a pending payment."""
        ...
