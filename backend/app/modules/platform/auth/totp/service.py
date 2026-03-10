"""2FA/TOTP service using pyotp + Fernet encryption for secrets."""

import uuid

import pyotp
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.encryption import decrypt_field, encrypt_field
from app.core.exceptions import AuthenticationError
from app.core.email import EmailSender, send_email_safe
from app.core.geoip import lookup_country
from app.core.security_emails import (
    build_2fa_disabled_email,
    build_2fa_enabled_email,
    check_and_alert_new_device,
    compute_device_fingerprint,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.core.schemas import TokenResponse
from app.modules.platform.auth.models import RefreshToken, User
from app.modules.platform.auth.totp.schemas import TwoFactorSetupConfirmed, TwoFactorSetupResponse

logger = structlog.get_logger()


def _encrypt_secret(secret: str) -> str:
    return encrypt_field(secret)


def _decrypt_secret(encrypted: str) -> str:
    return decrypt_field(encrypted)



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

    async def verify_2fa_setup(
        self, user: User, code: str,
        ip_address: str | None = None, user_agent: str | None = None,
    ) -> TwoFactorSetupConfirmed:
        """Verify TOTP code during setup and enable 2FA."""
        if not user.totp_secret_encrypted:
            raise AuthenticationError("Start eerst de 2FA-setup")

        secret = _decrypt_secret(user.totp_secret_encrypted)
        totp = pyotp.TOTP(secret)

        if not totp.verify(code, valid_window=1):
            raise AuthenticationError("Ongeldige verificatiecode")

        user.totp_enabled = True
        await self.db.flush()

        await self.audit.log("user.2fa_enabled", user_id=user.id)
        logger.info("2fa.enabled", user_id=str(user.id))

        # Send 2FA enabled notification
        try:
            subject, html = build_2fa_enabled_email(
                user.full_name, ip_address, user_agent,
            )
            await send_email_safe(user.email, subject, html, sender=EmailSender.SECURITY)
        except Exception:
            logger.warning("security_email.failed", action="2fa_enabled", user_id=str(user.id), exc_info=True)

        return TwoFactorSetupConfirmed(
            message="2FA is ingeschakeld. Bij verlies van je authenticator-app kun je inloggen via een e-mailcode.",
        )

    async def disable_2fa(
        self, user: User, password: str,
        ip_address: str | None = None, user_agent: str | None = None,
    ) -> None:
        """Disable 2FA. Requires password confirmation."""
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Onjuist wachtwoord")

        user.totp_enabled = False
        user.totp_secret_encrypted = None
        await self.db.flush()

        await self.audit.log("user.2fa_disabled", user_id=user.id)
        logger.info("2fa.disabled", user_id=str(user.id))

        # Send 2FA disabled notification
        try:
            subject, html = build_2fa_disabled_email(
                user.full_name, ip_address, user_agent,
            )
            await send_email_safe(user.email, subject, html, sender=EmailSender.SECURITY)
        except Exception:
            logger.warning("security_email.failed", action="2fa_disabled", user_id=str(user.id), exc_info=True)

    async def send_2fa_email_code(
        self,
        two_factor_token: str,
        purpose: str = "2fa_login",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> uuid.UUID:
        """Send a 6-digit verification code to the user's email for 2FA."""
        if purpose not in ("2fa_login", "2fa_recovery"):
            raise AuthenticationError("Ongeldig doel")

        try:
            payload = decode_token(two_factor_token)
        except Exception:
            raise AuthenticationError("Ongeldige of verlopen 2FA-token")

        if payload.get("type") != "2fa":
            raise AuthenticationError("Ongeldig tokentype")

        user_id = uuid.UUID(payload["sub"])
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise AuthenticationError("Gebruiker niet gevonden")

        if not user.email_verified:
            raise AuthenticationError("E-mail moet geverifieerd zijn voor email-verificatie")

        from app.modules.platform.auth.verification.service import VerificationCodeService
        verification_service = VerificationCodeService(self.db)
        verification_id = await verification_service.create_and_send(
            user, "email", purpose, ip_address=ip_address, user_agent=user_agent,
        )

        await self.audit.log(
            "2fa.email_code_sent",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            purpose=purpose,
        )

        return verification_id

    async def verify_2fa_login(
        self,
        two_factor_token: str,
        code: str,
        method: str = "totp",
        verification_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Verify 2FA code after login and issue tokens. Supports TOTP and email methods."""
        # Decode the 2fa token
        try:
            payload = decode_token(two_factor_token)
        except Exception:
            raise AuthenticationError("Ongeldige of verlopen 2FA-token")

        if payload.get("type") != "2fa":
            raise AuthenticationError("Ongeldig tokentype")

        user_id = uuid.UUID(payload["sub"])

        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active or not user.totp_enabled:
            raise AuthenticationError("Gebruiker niet gevonden of 2FA niet ingeschakeld")

        valid = False

        if method == "email":
            # Verify via email code
            if not verification_id:
                raise AuthenticationError("verification_id is vereist voor email-verificatie")
            from app.modules.platform.auth.verification.service import VerificationCodeService
            verification_service = VerificationCodeService(self.db)
            valid = await verification_service.verify(verification_id, code)

            await self.audit.log(
                "2fa.email_code_verified",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        elif method == "sms":
            # Verify via SMS code
            if not verification_id:
                raise AuthenticationError("verification_id is vereist voor SMS-verificatie")
            from app.modules.platform.auth.verification.service import VerificationCodeService
            verification_service = VerificationCodeService(self.db)
            valid = await verification_service.verify(verification_id, code)

            await self.audit.log(
                "2fa.sms_code_verified",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        else:
            # Try TOTP first
            secret = _decrypt_secret(user.totp_secret_encrypted)
            totp = pyotp.TOTP(secret)
            valid = totp.verify(code, valid_window=1)

            # Email recovery is available via the 'email' method

        if not valid:
            raise AuthenticationError("Ongeldige verificatiecode")

        # Issue tokens
        roles = []
        if user.is_superadmin:
            roles.append("super_admin")

        from app.modules.platform.auth.core.service import _hash_token

        # GeoIP country lookup
        country_code = lookup_country(ip_address)

        # Check for new device BEFORE inserting token
        await check_and_alert_new_device(
            self.db, str(user.id), user.email, user.full_name,
            user_agent, ip_address, country_code,
        )

        refresh_token, expires_at = create_refresh_token(user_id=user.id)
        fingerprint = compute_device_fingerprint(user_agent, country_code)

        token_hash = _hash_token(refresh_token)
        token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            device_fingerprint=fingerprint,
            country_code=country_code,
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


    async def send_2fa_sms_code(
        self,
        two_factor_token: str,
        purpose: str = "2fa_login",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> uuid.UUID:
        """Send a 6-digit verification code via SMS for 2FA."""
        if purpose not in ("2fa_login", "2fa_recovery"):
            raise AuthenticationError("Ongeldig doel")

        try:
            payload = decode_token(two_factor_token)
        except Exception:
            raise AuthenticationError("Ongeldige of verlopen 2FA-token")

        if payload.get("type") != "2fa":
            raise AuthenticationError("Ongeldig tokentype")

        user_id = uuid.UUID(payload["sub"])
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise AuthenticationError("Gebruiker niet gevonden")

        if not user.phone_number or not user.phone_verified:
            raise AuthenticationError("Geverifieerd telefoonnummer vereist voor SMS-verificatie")

        from app.modules.platform.auth.verification.service import VerificationCodeService
        verification_service = VerificationCodeService(self.db)
        verification_id = await verification_service.create_and_send(
            user, "sms", purpose, ip_address=ip_address, user_agent=user_agent,
        )

        await self.audit.log(
            "2fa.sms_code_sent",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            purpose=purpose,
        )

        return verification_id

    async def request_phone_verification(
        self,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> uuid.UUID:
        """Send a verification code to the user's phone number."""
        if not user.phone_number:
            raise AuthenticationError("Geen telefoonnummer gekoppeld aan dit account")

        if user.phone_verified:
            raise AuthenticationError("Telefoonnummer is al geverifieerd")

        from app.core.sms import is_sms_configured
        if not is_sms_configured():
            raise AuthenticationError("SMS is niet geconfigureerd")

        from app.modules.platform.auth.verification.service import VerificationCodeService
        verification_service = VerificationCodeService(self.db)
        verification_id = await verification_service.create_and_send(
            user, "sms", "phone_verify", ip_address=ip_address, user_agent=user_agent,
        )

        await self.audit.log(
            "phone.verification_sent",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return verification_id

    async def verify_phone(
        self,
        user: User,
        verification_id: uuid.UUID,
        code: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """Verify phone number with the code sent via SMS."""
        from app.modules.platform.auth.verification.service import VerificationCodeService
        verification_service = VerificationCodeService(self.db)
        await verification_service.verify(verification_id, code)

        user.phone_verified = True
        await self.db.flush()

        await self.audit.log(
            "phone.verified",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("phone.verified", user_id=str(user.id))
        return True


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
