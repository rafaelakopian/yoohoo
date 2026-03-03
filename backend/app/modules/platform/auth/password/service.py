"""Password reset and change service."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.email import send_email_safe
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.models import PasswordResetToken, RefreshToken, TenantMembership, User
from app.modules.platform.auth.password.schemas import ChangePasswordResponse
from app.modules.tenant.notification.templates import build_password_changed_email, build_password_reset_email

logger = structlog.get_logger()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PasswordService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def request_password_reset(
        self,
        email: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Request a password reset. Always succeeds (no email enumeration)."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not user.email_verified or not user.is_active:
            # Dummy token generation to equalize timing with the success path
            secrets.token_urlsafe(32)
            return  # Silent return to prevent enumeration

        # Check rate limit: max N tokens per hour per user
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at > cutoff,
            )
        )
        if len(recent.scalars().all()) >= settings.password_reset_rate_limit_per_hour:
            return  # Silent rate limit

        # Invalidate any existing unused tokens for this user
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                not PasswordResetToken.used,
            )
            .values(used=True)
        )

        # Generate token
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.password_reset_expire_minutes
        )

        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token_record)
        await self.db.flush()

        # Send email
        reset_url = f"{settings.frontend_url}/auth/reset-password?token={raw_token}"
        subject, html = build_password_reset_email(
            user.full_name, reset_url, settings.password_reset_expire_minutes
        )
        await send_email_safe(user.email, subject, html)

        await self.audit.log(
            "user.password_reset_requested",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("password.reset_requested", user_id=str(user.id))

    async def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Reset password using a token. Revokes all sessions."""
        token_hash = _hash_token(token)

        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                not PasswordResetToken.used,
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            raise AuthenticationError("Ongeldige of verlopen resetlink")

        if token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise AuthenticationError("Resetlink is verlopen")

        # Mark token as used
        token_record.used = True

        # Update password
        user_result = await self.db.execute(
            select(User).where(User.id == token_record.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise AuthenticationError("Gebruiker niet gevonden")

        user.hashed_password = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)

        # Revoke all refresh tokens (force re-login everywhere)
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, not RefreshToken.revoked)
            .values(revoked=True)
        )

        # Send confirmation email
        subject, html = build_password_changed_email(user.full_name)
        await send_email_safe(user.email, subject, html)

        await self.audit.log(
            "user.password_reset_completed",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("password.reset_completed", user_id=str(user.id))

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ChangePasswordResponse:
        """Change password for authenticated user. Returns new tokens."""
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Huidig wachtwoord is onjuist")

        # Update password
        user.hashed_password = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)

        # Revoke all existing refresh tokens
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, not RefreshToken.revoked)
            .values(revoked=True)
        )

        # Issue new tokens so session stays active
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

        access_token = create_access_token(
            user_id=user.id, email=user.email, roles=roles,
            user_agent=user_agent,
        )
        refresh_token, expires_at = create_refresh_token(user_id=user.id)

        # Store new refresh token
        token_hash = _hash_token(refresh_token)
        new_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
        self.db.add(new_record)

        # Send confirmation email
        subject, html = build_password_changed_email(user.full_name)
        await send_email_safe(user.email, subject, html)

        await self.audit.log(
            "user.password_changed",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.db.flush()

        logger.info("password.changed", user_id=str(user.id))

        return ChangePasswordResponse(
            message="Wachtwoord succesvol gewijzigd",
            access_token=access_token,
            refresh_token=refresh_token,
        )
