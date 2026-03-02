"""Payment provider factory — creates the correct provider instance per tenant."""

from app.modules.platform.billing.models import ProviderType
from app.modules.platform.billing.providers.base import PaymentProviderBase


class PaymentProviderFactory:
    """Factory to get the correct provider instance per tenant."""

    _PROVIDERS: dict[ProviderType, type[PaymentProviderBase]] = {}

    @classmethod
    def _ensure_registered(cls) -> None:
        """Lazy-load provider classes to avoid import cycles."""
        if cls._PROVIDERS:
            return
        from app.modules.platform.billing.providers.mollie import MollieProvider
        from app.modules.platform.billing.providers.stripe_provider import StripeProvider

        cls._PROVIDERS = {
            ProviderType.mollie: MollieProvider,
            ProviderType.stripe: StripeProvider,
        }

    @classmethod
    def create(
        cls,
        provider_type: ProviderType,
        api_key: str,
        api_secret: str | None = None,
        webhook_secret: str | None = None,
    ) -> PaymentProviderBase:
        cls._ensure_registered()
        provider_class = cls._PROVIDERS.get(provider_type)
        if not provider_class:
            raise ValueError(f"Unsupported provider: {provider_type}")
        return provider_class(
            api_key=api_key,
            api_secret=api_secret,
            webhook_secret=webhook_secret,
        )
