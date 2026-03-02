"""Tests for billing API key encryption (Fernet)."""

import pytest

from app.modules.platform.billing.encryption import decrypt_api_key, encrypt_api_key


@pytest.mark.asyncio
class TestBillingEncryption:
    async def test_encrypt_decrypt_round_trip(self):
        """Encrypting and decrypting should return the original value."""
        api_key = "test_mollie_api_key_12345"
        encrypted = encrypt_api_key(api_key)

        assert encrypted != api_key  # Should be different from plaintext
        assert len(encrypted) > 0

        decrypted = decrypt_api_key(encrypted)
        assert decrypted == api_key

    async def test_different_keys_produce_different_ciphertext(self):
        """Different plaintext keys should produce different ciphertext."""
        key1 = "mollie_key_abc"
        key2 = "stripe_key_xyz"

        enc1 = encrypt_api_key(key1)
        enc2 = encrypt_api_key(key2)

        assert enc1 != enc2

    async def test_encrypt_empty_string(self):
        """Edge case: encrypting an empty string should work."""
        encrypted = encrypt_api_key("")
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == ""

    async def test_encrypt_special_characters(self):
        """API keys may contain special characters."""
        api_key = "sk_live_51Abc+/=@#$%"
        encrypted = encrypt_api_key(api_key)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == api_key

    async def test_encrypt_long_key(self):
        """Some API keys can be long strings."""
        api_key = "a" * 500
        encrypted = encrypt_api_key(api_key)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == api_key
