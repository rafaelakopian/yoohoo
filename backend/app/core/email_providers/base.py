"""Abstract base class for email provider implementations."""

from abc import ABC, abstractmethod


class EmailProviderBase(ABC):
    """All email providers (SMTP, Resend, Brevo) implement this interface."""

    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        from_email: str,
        from_name: str,
    ) -> bool:
        """Send an email. Returns True on success, raises on failure."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (e.g. close httpx clients)."""
        ...
