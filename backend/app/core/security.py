import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import settings

# Argon2 for new hashes, Bcrypt for verifying existing hashes
password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def verify_and_update_password(plain_password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Verify password and return updated hash if rehash is needed (e.g. bcrypt → Argon2).
    Returns (is_valid, new_hash_or_none)."""
    valid, updated_hash = password_hash.verify_and_update(plain_password, hashed_password)
    return valid, updated_hash


def _ua_fingerprint(user_agent: str | None) -> str | None:
    """Create a short hash of the user-agent for token binding."""
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode()).hexdigest()[:16]


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    roles: list[str] | None = None,
    tenant_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    user_agent: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": roles or [],
        "tenant_id": str(tenant_id) if tenant_id else None,
        "session_id": str(session_id) if session_id else None,
        "type": "access",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "ua_fp": _ua_fingerprint(user_agent),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expire


def create_2fa_token(user_id: uuid.UUID) -> str:
    """Create a short-lived token for 2FA verification (5 minutes)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=5)
    payload = {
        "sub": str(user_id),
        "type": "2fa",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_login_verify_token(user_id: uuid.UUID, session_id: uuid.UUID) -> str:
    """Create a magic link token for login session verification (15 minutes)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.login_email_verification_expire_minutes)
    payload = {
        "sub": str(user_id),
        "session_id": str(session_id),
        "type": "login_verify",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
