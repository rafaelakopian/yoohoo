"""Tests for payment provider implementations (mock-based)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.platform.billing.providers.base import (
    CreatePaymentRequest,
    PaymentProviderBase,
    PaymentResult,
    RefundResult,
    WebhookVerificationResult,
)
from app.modules.platform.billing.providers import PaymentProviderFactory


@pytest.mark.asyncio
class TestPaymentProviderFactory:
    async def test_create_mollie_provider(self):
        provider = PaymentProviderFactory.create("mollie", api_key="test_key")
        assert provider is not None
        assert provider.api_key == "test_key"

    async def test_create_stripe_provider(self):
        provider = PaymentProviderFactory.create("stripe", api_key="sk_test_key")
        assert provider is not None
        assert provider.api_key == "sk_test_key"

    async def test_create_unknown_provider(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            PaymentProviderFactory.create("unknown", api_key="key")


@pytest.mark.asyncio
class TestMollieProviderStatusMapping:
    async def test_status_normalization(self):
        from app.modules.platform.billing.providers.mollie import MollieProvider

        provider = MollieProvider(api_key="test")
        assert provider._normalize_status("open") == "pending"
        assert provider._normalize_status("pending") == "processing"
        assert provider._normalize_status("authorized") == "processing"
        assert provider._normalize_status("paid") == "paid"
        assert provider._normalize_status("failed") == "failed"
        assert provider._normalize_status("canceled") == "cancelled"
        assert provider._normalize_status("expired") == "expired"
        assert provider._normalize_status("unknown") == "pending"


@pytest.mark.asyncio
class TestStripeProviderStatusMapping:
    async def test_status_normalization(self):
        from app.modules.platform.billing.providers.stripe_provider import StripeProvider

        provider = StripeProvider(api_key="sk_test")
        assert provider._normalize_status("requires_payment_method") == "pending"
        assert provider._normalize_status("requires_confirmation") == "pending"
        assert provider._normalize_status("requires_action") == "pending"
        assert provider._normalize_status("processing") == "processing"
        assert provider._normalize_status("requires_capture") == "processing"
        assert provider._normalize_status("succeeded") == "paid"
        assert provider._normalize_status("canceled") == "cancelled"
        assert provider._normalize_status("unknown") == "pending"


@pytest.mark.asyncio
class TestProviderBaseContract:
    async def test_base_class_stores_credentials(self):
        """Verify base class properly stores credentials."""

        class TestProvider(PaymentProviderBase):
            async def create_payment(self, r):
                pass
            async def get_payment(self, pid):
                pass
            async def create_refund(self, pid, a=None, d=None):
                pass
            async def verify_webhook(self, b, h):
                pass
            async def create_checkout_session(self, r):
                pass
            async def list_payment_methods(self, c=None):
                pass
            async def cancel_payment(self, pid):
                pass

        p = TestProvider(
            api_key="key", api_secret="secret", webhook_secret="wh_secret"
        )
        assert p.api_key == "key"
        assert p.api_secret == "secret"
        assert p.webhook_secret == "wh_secret"
