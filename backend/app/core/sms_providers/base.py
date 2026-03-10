"""Abstract base class for SMS provider implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SMSResult:
    """Normalized result from an SMS provider."""

    success: bool
    message_id: str | None = None
    provider: str = ""
    error: str | None = None


class SMSProviderBase(ABC):
    """All SMS providers (Brevo, Twilio, Vonage, etc.) implement this interface."""

    @abstractmethod
    async def send(self, to: str, message: str, sender: str) -> SMSResult:
        """Send an SMS. Returns SMSResult with delivery status."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (e.g. close httpx clients)."""
        ...
