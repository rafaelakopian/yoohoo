"""Fernet encryption for payment provider API keys.

Delegates to the centralized encryption utility in app.core.encryption.
"""

from app.core.encryption import decrypt_field, encrypt_field


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt a payment provider API key."""
    return encrypt_field(plaintext)


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt a payment provider API key."""
    return decrypt_field(encrypted)
