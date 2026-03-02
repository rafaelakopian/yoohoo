"""Centralized field encryption using Fernet with PBKDF2 key derivation.

Used for encrypting sensitive data at rest (TOTP secrets, API keys, etc.).
Provides backwards-compatible decryption for data encrypted with the old
SHA256-only key derivation.
"""

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.config import settings

# Fixed salt for PBKDF2 — changing this invalidates all encrypted data.
# In a production KMS setup, this would be stored separately.
_PBKDF2_SALT = b"yoohoo-field-encryption-v1"
_PBKDF2_ITERATIONS = 100_000


def _derive_key_pbkdf2() -> bytes:
    """Derive a Fernet key from settings.secret_key using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_PBKDF2_SALT,
        iterations=_PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))


def _derive_key_legacy() -> bytes:
    """Legacy key derivation (plain SHA256) for backwards compatibility."""
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key)


def _get_fernet() -> Fernet:
    """Get a Fernet instance using PBKDF2-derived key."""
    return Fernet(_derive_key_pbkdf2())


def _get_fernet_legacy() -> Fernet:
    """Get a Fernet instance using legacy SHA256-derived key."""
    return Fernet(_derive_key_legacy())


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string value for storage. Uses PBKDF2 key derivation."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(encrypted: str) -> str:
    """Decrypt a stored value. Tries PBKDF2 first, falls back to legacy SHA256."""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        # Backwards compatibility: try legacy SHA256-only derivation
        return _get_fernet_legacy().decrypt(encrypted.encode()).decode()


def hmac_hash(value: str) -> str:
    """HMAC-SHA256 hash for lookup on encrypted fields (deterministic)."""
    return hmac.new(
        settings.secret_key.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()
