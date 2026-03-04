import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.email import EmailSender, build_verification_email, send_email
from app.core.event_bus import event_bus
from app.core.security_emails import check_and_alert_new_device, compute_device_fingerprint
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.login_throttle import check_login_allowed, clear_failed_attempts, record_failed_attempt
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_and_update_password,
    verify_password,
)
from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.models import (
    PermissionGroup,
    RefreshToken,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.core.schemas import DeleteAccount, LoginResponse, RequestEmailChange, TokenResponse, UpdateProfile, UserRegister

logger = structlog.get_logger()


def _hash_token(token: str) -> str:
    """HMAC-SHA256 token hash using the application secret key."""
    return hmac.new(
        settings.secret_key.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def _hash_token_legacy(token: str) -> str:
    """Legacy plain SHA256 hash — used for backwards-compatible lookups."""
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_verification_token() -> tuple[str, str, datetime]:
    """Generate a verification token, its hash, and expiry datetime."""
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.email_verification_expire_hours
    )
    return token, token_hash, expires_at


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserRegister) -> tuple[User | None, str | None]:
        """Register a new user. Returns (user, verification_token) or (None, None) if email taken."""
        existing = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        if existing.scalar_one_or_none():
            # Don't reveal email existence — return None silently
            # Perform a dummy hash to equalize timing with the success path
            hash_password(data.password)
            logger.info("user.register_duplicate", email=data.email)
            return None, None

        token, token_hash, expires_at = _generate_verification_token()

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            email_verified=False,
            verification_token_hash=token_hash,
            verification_token_expires_at=expires_at,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info("user.registered", user_id=str(user.id), email=user.email)
        await event_bus.emit("user.registered", user_id=user.id, email=user.email)

        return user, token

    async def send_verification_email(self, user: User, token: str) -> None:
        """Send verification email (called from BackgroundTasks)."""
        subject, html = build_verification_email(user.full_name, token)
        await send_email(user.email, subject, html, sender=EmailSender.ACCOUNT)

    async def verify_email(self, token: str) -> User:
        """Verify a user's email address using the token."""
        token_hash = _hash_token(token)

        result = await self.db.execute(
            select(User).where(User.verification_token_hash == token_hash)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise AuthenticationError("Ongeldige of verlopen verificatielink")

        if user.email_verified:
            return user

        if (
            user.verification_token_expires_at is None
            or user.verification_token_expires_at.replace(tzinfo=timezone.utc)
            < datetime.now(timezone.utc)
        ):
            raise AuthenticationError("Verificatielink is verlopen. Vraag een nieuwe aan.")

        user.email_verified = True
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        await self.db.flush()

        logger.info("user.email_verified", user_id=str(user.id), email=user.email)
        return user

    async def resend_verification(self, email: str) -> str | None:
        """Resend verification email. Returns token if user found and unverified, else None.
        Always returns None to caller to prevent email enumeration — the router
        gives the same response regardless."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user or user.email_verified:
            return None

        token, token_hash, expires_at = _generate_verification_token()
        user.verification_token_hash = token_hash
        user.verification_token_expires_at = expires_at
        await self.db.flush()

        return token

    async def login(
        self, email: str, password: str, ip_address: str | None = None, user_agent: str | None = None,
        redis=None, remember_me: bool = False,
    ) -> LoginResponse:
        # Brute force check
        if not await check_login_allowed(email, redis):
            raise AuthenticationError(
                "Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw."
            )

        user = await self._get_user_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            await record_failed_attempt(email, redis)
            raise AuthenticationError("Invalid email or password")

        if not user.email_verified:
            raise AuthenticationError("E-mailadres is nog niet geverifieerd. Controleer je inbox.")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Enforce MFA for superadmins
        if user.is_superadmin and not user.totp_enabled:
            raise AuthenticationError(
                "Superadmin-accounts vereisen tweefactorauthenticatie. "
                "Neem contact op met een andere admin om 2FA in te schakelen."
            )

        # Transparently rehash from bcrypt to Argon2 on login
        _, updated_hash = verify_and_update_password(password, user.hashed_password)
        if updated_hash:
            user.hashed_password = updated_hash
            await self.db.flush()

        # Check if 2FA is enabled
        if user.totp_enabled:
            # Return a short-lived 2FA token instead of access/refresh tokens
            from app.core.security import create_2fa_token
            two_factor_token = create_2fa_token(user_id=user.id)
            methods = ["totp"]
            if user.email_verified:
                methods.append("email")
            return LoginResponse(
                requires_2fa=True,
                two_factor_token=two_factor_token,
                available_2fa_methods=methods,
            )

        # Clear brute force counter on successful credential check
        await clear_failed_attempts(email, redis)

        # Determine session type based on remember_me
        session_type = "persistent" if remember_me else "session"
        if session_type == "session":
            expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_default_hours)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_remember_me_days)

        # Check for new device BEFORE inserting token
        await check_and_alert_new_device(
            self.db, str(user.id), user.email, user.full_name,
            user_agent, ip_address,
        )

        # Email verification flow (non-2FA users, when toggle is enabled)
        if settings.login_require_email_verification:
            # Revoke any previous unverified sessions for this user
            from sqlalchemy import update
            await self.db.execute(
                update(RefreshToken).where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.verified.is_(False),
                    RefreshToken.revoked.is_(False),
                ).values(revoked=True)
            )

            refresh_token, _ = create_refresh_token(user_id=user.id)
            fingerprint = compute_device_fingerprint(user_agent)

            token_record = RefreshToken(
                user_id=user.id,
                token_hash=_hash_token(refresh_token),
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
                device_fingerprint=fingerprint,
                session_type=session_type,
                verified=False,
            )
            self.db.add(token_record)
            await self.db.flush()

            # Generate magic link token
            from app.core.security import create_login_verify_token
            from app.core.security_emails import build_login_verification_email
            from app.core.email import send_email_safe, EmailSender

            verify_token = create_login_verify_token(user.id, token_record.id)
            verify_url = f"{settings.frontend_url}/auth/verify-session?token={verify_token}"

            subject, html = build_login_verification_email(
                user.full_name, verify_url, ip_address, user_agent,
            )
            await send_email_safe(user.email, subject, html, sender=EmailSender.SECURITY)

            user.last_login_at = datetime.now(timezone.utc)
            await self.db.flush()

            audit = AuditService(self.db)
            await audit.log(
                "user.login_pending_verification",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            logger.info("user.login_pending_verification", user_id=str(user.id))

            return LoginResponse(
                requires_email_verification=True,
            )

        # Direct login flow (toggle off or fallback)
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

        refresh_token, _ = create_refresh_token(user_id=user.id)
        fingerprint = compute_device_fingerprint(user_agent)

        token_record = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh_token),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            device_fingerprint=fingerprint,
            session_type=session_type,
        )
        self.db.add(token_record)

        user.last_login_at = datetime.now(timezone.utc)

        await self.db.flush()

        # Enforce max active sessions (FIFO: revoke oldest)
        await self._enforce_max_sessions(user.id)

        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=roles,
            session_id=token_record.id,
            user_agent=user_agent,
        )

        logger.info("user.logged_in", user_id=str(user.id))

        audit = AuditService(self.db)
        await audit.log(
            "user.login",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh(
        self, refresh_token: str, ip_address: str | None = None, user_agent: str | None = None
    ) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise AuthenticationError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        token_record = await self._find_token(refresh_token)
        if not token_record:
            raise AuthenticationError("Refresh token not found or revoked")

        if token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise AuthenticationError("Refresh token expired")

        # Reject unverified sessions (pending email verification)
        if not token_record.verified:
            raise AuthenticationError("Sessie niet geverifieerd")

        # Track session activity
        token_record.last_used_at = datetime.now(timezone.utc)

        # Revoke old token (rotation)
        token_record.revoked = True

        user = await self._get_user_by_id(token_record.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or deactivated")

        # Issue new tokens
        roles = []
        if user.is_superadmin:
            roles.append(Role.SUPER_ADMIN.value)

        new_refresh_token, expires_at = create_refresh_token(user_id=user.id)

        new_record = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(new_refresh_token),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            device_fingerprint=compute_device_fingerprint(user_agent),
            last_used_at=datetime.now(timezone.utc),
            session_type=token_record.session_type,
            verified=True,
        )
        self.db.add(new_record)
        await self.db.flush()

        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=roles,
            session_id=new_record.id,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    async def logout(self, refresh_token: str) -> None:
        token_record = await self._find_token(refresh_token, include_revoked=True)
        if token_record:
            token_record.revoked = True
            await self.db.flush()

    async def verify_login_session(
        self, token: str, ip_address: str | None = None, user_agent: str | None = None,
    ) -> LoginResponse:
        """Verify a magic link token and activate the session."""
        try:
            payload = decode_token(token)
        except Exception:
            raise AuthenticationError("Ongeldige of verlopen link")

        if payload.get("type") != "login_verify":
            raise AuthenticationError("Ongeldig tokentype")

        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["session_id"])

        # Look up the pending session
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.id == session_id,
                RefreshToken.user_id == user_id,
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            raise AuthenticationError("Sessie niet gevonden")

        if token_record.revoked:
            raise AuthenticationError("Sessie is al ongeldig gemaakt")

        if token_record.verified:
            raise AuthenticationError("Sessie is al geverifieerd")

        if token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise AuthenticationError("Sessie is verlopen")

        # Activate session
        token_record.verified = True
        token_record.last_used_at = datetime.now(timezone.utc)

        user = await self._get_user_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Gebruiker niet gevonden of gedeactiveerd")

        # Issue tokens for the verifier
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

        # Create a fresh refresh token for the verifier (the original hash was never sent to client)
        refresh_token, expires_at = create_refresh_token(user_id=user.id)
        fingerprint = compute_device_fingerprint(user_agent)

        new_record = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh_token),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            device_fingerprint=fingerprint,
            session_type=token_record.session_type,
            verified=True,
        )
        self.db.add(new_record)
        await self.db.flush()

        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=roles,
            session_id=new_record.id,
            user_agent=user_agent,
        )

        audit = AuditService(self.db)
        await audit.log(
            "user.login_session_verified",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("user.login_session_verified", user_id=str(user.id))

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def get_user_with_memberships(self, user_id: uuid.UUID) -> User:
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.memberships),
                selectinload(User.group_assignments)
                .selectinload(UserGroupAssignment.group)
                .selectinload(PermissionGroup.permissions),
            )
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))
        return user

    async def update_profile(
        self,
        user: User,
        data: UpdateProfile,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Update user profile fields."""
        changes = {}
        if data.full_name is not None and data.full_name != user.full_name:
            changes["full_name"] = data.full_name
            user.full_name = data.full_name

        if changes:
            await self.db.flush()
            audit = AuditService(self.db)
            await audit.log(
                "user.profile_updated",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                **changes,
            )
            logger.info("user.profile_updated", user_id=str(user.id))

        return user

    async def delete_account(
        self,
        user: User,
        data: DeleteAccount,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Soft-delete/anonymize user account. Requires password confirmation."""
        if not verify_password(data.password, user.hashed_password):
            raise AuthenticationError("Onjuist wachtwoord")

        # Check if user is a tenant owner
        from app.modules.platform.tenant_mgmt.models import Tenant
        result = await self.db.execute(
            select(Tenant).where(Tenant.owner_id == user.id)
        )
        owned_tenants = result.scalars().all()
        if owned_tenants:
            names = ", ".join(t.name for t in owned_tenants)
            raise ConflictError(
                f"Je bent eigenaar van: {names}. Draag het eigenaarschap eerst over voordat je je account verwijdert."
            )

        # Revoke all sessions
        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked.is_(False),
            ).values(revoked=True)
        )

        # Delete group assignments
        await self.db.execute(
            delete(UserGroupAssignment).where(UserGroupAssignment.user_id == user.id)
        )

        # Delete memberships
        await self.db.execute(
            delete(TenantMembership).where(TenantMembership.user_id == user.id)
        )

        # Audit before anonymization
        audit = AuditService(self.db)
        await audit.log(
            "user.account_deleted",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            email=user.email,
        )

        # Anonymize user (soft delete)
        user.email = f"deleted_{user.id}@deleted"
        user.full_name = "Verwijderd"
        user.is_active = False
        user.hashed_password = "DELETED"
        user.totp_enabled = False
        user.totp_secret_encrypted = None
        user.backup_codes_hash = None
        user.pending_email = None
        user.pending_email_token_hash = None
        user.pending_email_token_expires_at = None
        user.verification_token_hash = None
        user.verification_token_expires_at = None

        await self.db.flush()
        logger.info("user.account_deleted", user_id=str(user.id))

    async def request_email_change(
        self,
        user: User,
        data: RequestEmailChange,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Request an email change. Returns the verification token for the new email."""
        if not verify_password(data.password, user.hashed_password):
            raise AuthenticationError("Onjuist wachtwoord")

        if data.new_email == user.email:
            raise ConflictError("Het nieuwe e-mailadres is hetzelfde als het huidige")

        # Check if new email is already taken — don't reveal this to prevent enumeration
        existing = await self._get_user_by_email(data.new_email)
        if existing:
            logger.info("user.email_change_duplicate", email=data.new_email)
            # Return a dummy token — the verification email won't be sent to an existing user
            return secrets.token_urlsafe(32)

        token, token_hash, expires_at = _generate_verification_token()
        user.pending_email = data.new_email
        user.pending_email_token_hash = token_hash
        user.pending_email_token_expires_at = expires_at
        await self.db.flush()

        audit = AuditService(self.db)
        await audit.log(
            "user.email_change_requested",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            new_email=data.new_email,
        )
        logger.info("user.email_change_requested", user_id=str(user.id), new_email=data.new_email)

        return token

    async def send_email_change_verification(self, user: User, new_email: str, token: str) -> None:
        """Send verification email for email change to the NEW email address."""
        from app.modules.tenant.notification.templates import _base_template
        from app.core.email import escape

        confirm_url = f"{settings.frontend_url}/auth/confirm-email-change?token={token}"
        subject = f"Bevestig je nieuwe e-mailadres — {settings.platform_name}"
        body = f"""
        <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(user.full_name)},</p>
        <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 24px;">
          Je hebt gevraagd om je e-mailadres te wijzigen naar <strong>{escape(new_email)}</strong>.
          Klik op de knop hieronder om dit te bevestigen.
        </p>
        <table cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
          <tr><td align="center" style="background-color:#cd095b;border-radius:8px;">
            <a href="{confirm_url}" style="display:inline-block;padding:14px 32px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:bold;">
              Nieuw e-mailadres bevestigen
            </a>
          </td></tr>
        </table>
        <p style="color:#767a81;font-size:13px;line-height:1.5;margin:0 0 8px;">
          Of kopieer deze link in je browser:
        </p>
        <p style="color:#066aab;font-size:13px;word-break:break-all;margin:0 0 24px;">
          {confirm_url}
        </p>
        <p style="color:#979da8;font-size:12px;margin:0;">
          Deze link is {settings.email_verification_expire_hours} uur geldig.
          Als je dit niet hebt aangevraagd, kun je deze e-mail negeren.
        </p>"""
        html = _base_template("E-mailadres wijzigen", body)
        await send_email(new_email, subject, html, sender=EmailSender.ACCOUNT)

    async def confirm_email_change(
        self,
        token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str]:
        """Confirm an email change using the verification token."""
        token_hash = _hash_token(token)

        result = await self.db.execute(
            select(User).where(User.pending_email_token_hash == token_hash)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise AuthenticationError("Ongeldige of verlopen link")

        if not user.pending_email or not user.pending_email_token_expires_at:
            raise AuthenticationError("Geen e-mailwijziging in behandeling")

        if user.pending_email_token_expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise AuthenticationError("Link is verlopen. Vraag een nieuwe wijziging aan.")

        # Check if new email is still available
        existing = await self._get_user_by_email(user.pending_email)
        if existing:
            raise ConflictError("Dit e-mailadres is inmiddels al in gebruik")

        old_email = user.email
        user.email = user.pending_email
        user.pending_email = None
        user.pending_email_token_hash = None
        user.pending_email_token_expires_at = None

        # Revoke all sessions (email changed = security event)
        from sqlalchemy import update
        await self.db.execute(
            update(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked.is_(False),
            ).values(revoked=True)
        )

        await self.db.flush()

        audit = AuditService(self.db)
        await audit.log(
            "user.email_changed",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_email=old_email,
            new_email=user.email,
        )
        logger.info("user.email_changed", user_id=str(user.id), old_email=old_email, new_email=user.email)

        return user, old_email

    async def send_email_changed_notification(self, full_name: str, old_email: str) -> None:
        """Send notification to the OLD email address that email was changed."""
        from app.modules.tenant.notification.templates import _base_template
        from app.core.email import escape

        subject = f"Je e-mailadres is gewijzigd — {settings.platform_name}"
        body = f"""
        <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
        <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 24px;">
          Het e-mailadres van je account is zojuist gewijzigd. Dit adres ({escape(old_email)}) is niet meer gekoppeld aan je account.
        </p>
        <p style="color:#979da8;font-size:12px;margin:0;">
          Als je dit niet zelf hebt gedaan, neem dan direct contact op met de beheerder.
        </p>"""
        html = _base_template("E-mailadres gewijzigd", body)
        await send_email(old_email, subject, html, sender=EmailSender.SECURITY)

    async def _enforce_max_sessions(self, user_id: uuid.UUID) -> None:
        """Revoke oldest sessions if user exceeds MAX_ACTIVE_SESSIONS."""
        result = await self.db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .order_by(RefreshToken.created_at.asc())
        )
        active_tokens = result.scalars().all()
        excess = len(active_tokens) - settings.max_active_sessions
        if excess > 0:
            for token in active_tokens[:excess]:
                token.revoked = True
            await self.db.flush()
            logger.info(
                "session.max_enforced",
                user_id=str(user_id),
                revoked=excess,
            )

    async def _find_token(self, raw_token: str, include_revoked: bool = False) -> RefreshToken | None:
        """Look up a refresh token by hash. Tries HMAC first, falls back to legacy SHA256."""
        for hash_fn in (_hash_token, _hash_token_legacy):
            token_hash = hash_fn(raw_token)
            query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            if not include_revoked:
                query = query.where(RefreshToken.revoked.is_(False))
            result = await self.db.execute(query)
            record = result.scalar_one_or_none()
            if record:
                # Migrate legacy hash to HMAC on first hit
                if hash_fn is _hash_token_legacy:
                    record.token_hash = _hash_token(raw_token)
                    await self.db.flush()
                return record
        return None

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def cleanup_unverified_users(db: AsyncSession) -> int:
    """Delete users that have not verified their email within the cleanup window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.unverified_cleanup_days)
    result = await db.execute(
        delete(User).where(
            User.email_verified.is_(False),
            User.created_at < cutoff,
        )
    )
    count = result.rowcount
    if count:
        logger.info("cleanup.unverified_users", deleted=count)
    await db.commit()
    return count
