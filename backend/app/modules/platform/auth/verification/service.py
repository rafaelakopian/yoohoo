"""Channel-agnostic verification code service for 2FA email codes, recovery, and phone verify."""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.email import EmailSender, escape, send_email
from app.core.exceptions import AuthenticationError, RateLimitError
from app.modules.platform.auth.models import User, VerificationCode

logger = structlog.get_logger()

_PURPOSE_SUBJECTS = {
    "2fa_login": "Verificatiecode voor inloggen",
    "2fa_recovery": "Herstelcode voor je account",
    "phone_verify": "Verificatiecode voor telefoonnummer",
}


def _hash_code(code: str) -> str:
    """HMAC-SHA256 hash a verification code."""
    return hmac.new(
        settings.secret_key.encode(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()


def _mask_email(email: str) -> str:
    """Mask email for audit: 'user@example.com' → 'u***@example.com'."""
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def _generate_code(length: int = 6) -> str:
    """Generate a numeric verification code."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


class VerificationCodeService:
    """Manages creation, sending, and validation of verification codes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_and_send(
        self,
        user: User,
        channel: str,
        purpose: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> uuid.UUID:
        """Generate a code, store it, send via channel, return the record ID.

        Raises RateLimitError if a code was sent less than cooldown_seconds ago.
        """
        # 1. Rate limit: check cooldown
        cooldown = timedelta(seconds=settings.verification_code_cooldown_seconds)
        cutoff = datetime.now(timezone.utc) - cooldown
        recent = await self.db.execute(
            select(VerificationCode).where(
                VerificationCode.user_id == user.id,
                VerificationCode.purpose == purpose,
                VerificationCode.created_at > cutoff,
            )
        )
        if recent.scalar_one_or_none():
            raise RateLimitError("Wacht even voordat je een nieuwe code aanvraagt")

        # 2. Invalidate previous unused codes for same user+purpose+channel
        await self.db.execute(
            update(VerificationCode)
            .where(
                VerificationCode.user_id == user.id,
                VerificationCode.purpose == purpose,
                VerificationCode.channel == channel,
                VerificationCode.used.is_(False),
            )
            .values(used=True)
        )

        # 3. Generate code
        code = _generate_code()
        code_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.verification_code_expire_minutes
        )

        # 4. Determine sent_to (masked)
        if channel == "email":
            sent_to = _mask_email(user.email)
        else:
            sent_to = f"***{user.phone_number[-4:]}" if user.phone_number else None

        # 5. Store
        record = VerificationCode(
            user_id=user.id,
            channel=channel,
            purpose=purpose,
            code_hash=code_hash,
            sent_to=sent_to,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
        self.db.add(record)
        await self.db.flush()

        # 6. Send
        if channel == "email":
            await self._send_via_email(user, code, purpose)
        elif channel == "sms":
            await self._send_via_sms(user, code, purpose)
        else:
            raise ValueError(f"Unknown channel: {channel}")

        logger.info(
            "verification_code.sent",
            user_id=str(user.id),
            channel=channel,
            purpose=purpose,
            code_id=str(record.id),
        )
        return record.id

    async def verify(self, verification_id: uuid.UUID, code: str) -> bool:
        """Validate a verification code by its record ID.

        Returns True on success, raises AuthenticationError on failure.
        """
        result = await self.db.execute(
            select(VerificationCode).where(VerificationCode.id == verification_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            raise AuthenticationError("Ongeldige verificatiecode")

        if record.used:
            raise AuthenticationError("Deze code is al gebruikt")

        if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise AuthenticationError("Deze code is verlopen")

        if record.attempts >= settings.verification_code_max_attempts:
            record.used = True  # Lock out this code
            await self.db.flush()
            raise AuthenticationError("Te veel pogingen. Vraag een nieuwe code aan.")

        # Increment attempts
        record.attempts += 1

        # Timing-safe comparison
        if not hmac.compare_digest(_hash_code(code), record.code_hash):
            await self.db.flush()
            remaining = settings.verification_code_max_attempts - record.attempts
            raise AuthenticationError(
                f"Onjuiste code. Nog {remaining} poging(en) over."
            )

        # Success
        record.used = True
        await self.db.flush()

        logger.info(
            "verification_code.verified",
            code_id=str(verification_id),
            user_id=str(record.user_id),
            purpose=record.purpose,
        )
        return True

    async def _send_via_email(self, user: User, code: str, purpose: str) -> None:
        """Send verification code via email."""
        from app.modules.products.school.notification.templates import _base_template

        subject_text = _PURPOSE_SUBJECTS.get(purpose, "Verificatiecode")
        subject = f"{subject_text} — {settings.platform_name}"

        body = f"""
        <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(user.full_name)},</p>
        <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 24px;">
          Gebruik de volgende code om verder te gaan:
        </p>
        <div style="text-align:center;margin:0 0 24px;">
          <span style="display:inline-block;background:#f3f4f6;border-radius:8px;padding:16px 32px;font-size:32px;font-weight:bold;letter-spacing:8px;color:#202b40;font-family:monospace;">
            {code}
          </span>
        </div>
        <p style="color:#767a81;font-size:13px;line-height:1.5;margin:0 0 8px;">
          Deze code is {settings.verification_code_expire_minutes} minuten geldig.
        </p>
        <p style="color:#979da8;font-size:12px;margin:0;">
          Als je dit niet hebt aangevraagd, kun je deze e-mail negeren.
        </p>"""

        html = _base_template(subject_text, body)
        await send_email(user.email, subject, html, sender=EmailSender.SECURITY)

    async def _send_via_sms(self, user: User, code: str, purpose: str) -> None:
        """Send verification code via SMS."""
        from app.core.sms import is_sms_configured, send_sms_safe

        if not is_sms_configured():
            raise NotImplementedError("SMS provider niet geconfigureerd")

        if not user.phone_number:
            raise ValueError("Geen telefoonnummer gekoppeld aan dit account")

        subject_text = _PURPOSE_SUBJECTS.get(purpose, "Verificatiecode")
        message = f"{settings.platform_name}: {subject_text}. Code: {code}. Geldig voor {settings.verification_code_expire_minutes} min."

        success = await send_sms_safe(user.phone_number, message)
        if not success:
            raise RuntimeError("SMS kon niet worden verzonden")
