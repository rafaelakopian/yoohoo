"""2FA/TOTP service using pyotp + Fernet encryption for secrets."""

import hashlib
import json
import secrets

import pyotp
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.encryption import decrypt_field, encrypt_field
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.core.schemas import TokenResponse
from app.modules.platform.auth.models import RefreshToken, TenantMembership, User
from app.modules.platform.auth.totp.schemas import TwoFactorBackupCodes, TwoFactorSetupResponse

logger = structlog.get_logger()


def _encrypt_secret(secret: str) -> str:
    return encrypt_field(secret)


def _decrypt_secret(encrypted: str) -> str:
    return decrypt_field(encrypted)


def _hash_backup_code(code: str) -> str:
    """Hash a backup code using SHA256 (fast but sufficient for single-use codes)."""
    return hashlib.sha256(code.encode()).hexdigest()


class TOTPService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def setup_2fa(self, user: User) -> TwoFactorSetupResponse:
        """Generate a TOTP secret and provisioning URI. Not yet enabled."""
        if user.totp_enabled:
            from app.core.exceptions import ConflictError
            raise ConflictError("2FA is al actief. Schakel het eerst uit.")

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=settings.totp_issuer_name or settings.platform_name,
        )

        # Store encrypted secret (not enabled until verified)
        user.totp_secret_encrypted = _encrypt_secret(secret)
        await self.db.flush()

        # Generate a QR code data URI
        qr_uri = _generate_qr_data_uri(provisioning_uri)

        return TwoFactorSetupResponse(
            secret=secret,
            qr_code_uri=qr_uri,
        )

    async def verify_2fa_setup(self, user: User, code: str) -> TwoFactorBackupCodes:
        """Verify TOTP code during setup, enable 2FA, and return backup codes."""
        if not user.totp_secret_encrypted:
            raise AuthenticationError("Start eerst de 2FA-setup")

        secret = _decrypt_secret(user.totp_secret_encrypted)
        totp = pyotp.TOTP(secret)

        if not totp.verify(code, valid_window=1):
            raise AuthenticationError("Ongeldige verificatiecode")

        # Generate backup codes
        backup_codes = [secrets.token_hex(6) for _ in range(settings.totp_backup_code_count)]
        hashed_codes = [_hash_backup_code(c) for c in backup_codes]

        user.totp_enabled = True
        user.backup_codes_hash = json.dumps(hashed_codes)
        await self.db.flush()

        await self.audit.log("user.2fa_enabled", user_id=user.id)
        logger.info("2fa.enabled", user_id=str(user.id))

        return TwoFactorBackupCodes(
            backup_codes=backup_codes,
            message="2FA is ingeschakeld. Bewaar je back-upcodes op een veilige plek.",
        )

    async def regenerate_backup_codes(self, user: User, password: str) -> TwoFactorBackupCodes:
        """Regenerate backup codes. Requires 2FA to be enabled and password confirmation."""
        if not user.totp_enabled:
            raise AuthenticationError("2FA is niet ingeschakeld")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Onjuist wachtwoord")

        backup_codes = [secrets.token_hex(6) for _ in range(settings.totp_backup_code_count)]
        hashed_codes = [_hash_backup_code(c) for c in backup_codes]

        user.backup_codes_hash = json.dumps(hashed_codes)
        await self.db.flush()

        await self.audit.log("user.2fa_backup_regenerated", user_id=user.id)
        logger.info("2fa.backup_regenerated", user_id=str(user.id))

        return TwoFactorBackupCodes(
            backup_codes=backup_codes,
            message="Nieuwe back-upcodes gegenereerd. Bewaar ze op een veilige plek.",
        )

    async def disable_2fa(self, user: User, password: str) -> None:
        """Disable 2FA. Requires password confirmation."""
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Onjuist wachtwoord")

        user.totp_enabled = False
        user.totp_secret_encrypted = None
        user.backup_codes_hash = None
        await self.db.flush()

        await self.audit.log("user.2fa_disabled", user_id=user.id)
        logger.info("2fa.disabled", user_id=str(user.id))

    async def verify_2fa_login(
        self,
        two_factor_token: str,
        code: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Verify TOTP code after login and issue tokens."""
        # Decode the 2fa token
        try:
            payload = decode_token(two_factor_token)
        except Exception:
            raise AuthenticationError("Ongeldige of verlopen 2FA-token")

        if payload.get("type") != "2fa":
            raise AuthenticationError("Ongeldig tokentype")

        import uuid
        user_id = uuid.UUID(payload["sub"])

        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active or not user.totp_enabled:
            raise AuthenticationError("Gebruiker niet gevonden of 2FA niet ingeschakeld")

        # Try TOTP first
        secret = _decrypt_secret(user.totp_secret_encrypted)
        totp = pyotp.TOTP(secret)
        valid = totp.verify(code, valid_window=1)

        # If TOTP fails, try backup codes
        if not valid:
            valid = await self._try_backup_code(user, code)

        if not valid:
            raise AuthenticationError("Ongeldige verificatiecode")

        # Issue tokens
        roles = []
        if user.is_superadmin:
            roles.append(Role.SUPER_ADMIN.value)

        memberships = await self.db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user.id,
                TenantMembership.is_active,
            )
        )
        for m in memberships.scalars().all():
            if m.role:
                roles.append(m.role.value)

        from app.modules.platform.auth.core.service import _hash_token

        refresh_token, expires_at = create_refresh_token(user_id=user.id)

        token_hash = _hash_token(refresh_token)
        token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
        self.db.add(token_record)
        await self.db.flush()

        access_token = create_access_token(
            user_id=user.id, email=user.email, roles=roles,
            session_id=token_record.id,
            user_agent=user_agent,
        )

        await self.audit.log(
            "user.login",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            method="2fa",
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def _try_backup_code(self, user: User, code: str) -> bool:
        """Try to use a backup code. Removes it if valid."""
        if not user.backup_codes_hash:
            return False

        hashed_codes: list[str] = json.loads(user.backup_codes_hash)
        code_hash = _hash_backup_code(code)

        if code_hash in hashed_codes:
            hashed_codes.remove(code_hash)
            user.backup_codes_hash = json.dumps(hashed_codes)
            await self.db.flush()

            await self.audit.log("user.2fa_backup_used", user_id=user.id)
            logger.info("2fa.backup_used", user_id=str(user.id))
            return True

        return False


def _generate_qr_data_uri(data: str) -> str:
    """Generate a QR code as a data URI using a simple SVG-based approach."""
    try:
        import io
        import base64
        # Use segno for QR generation (pure Python, small)
        # Fallback: just return the provisioning URI for the frontend to handle
        try:
            import segno
            qr = segno.make(data)
            buffer = io.BytesIO()
            qr.save(buffer, kind="png", scale=6, border=2)
            buffer.seek(0)
            b64 = base64.b64encode(buffer.read()).decode()
            return f"data:image/png;base64,{b64}"
        except ImportError:
            # If segno is not available, return the raw URI
            # Frontend can use a JS QR library
            return data
    except Exception:
        return data
