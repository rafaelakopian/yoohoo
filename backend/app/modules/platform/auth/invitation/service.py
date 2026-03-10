"""Invitation service for invite-only organization membership."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.email import EmailSender, send_email_safe
from app.core.encryption import hmac_hash
from app.core.exceptions import AuthenticationError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.dependencies import is_platform_user
from app.modules.platform.auth.models import Invitation, PermissionGroup, TenantMembership, User, UserGroupAssignment
from app.modules.platform.auth.invitation.schemas import (
    AcceptInvitationResponse,
    BulkInvitationResponse,
    BulkInvitationResult,
    InvitationResponse,
    InvitationWithStatus,
    InviteInfo,
)
from app.modules.products.school.notification.templates import build_invitation_email
from app.modules.platform.tenant_mgmt.models import Tenant

logger = structlog.get_logger()


def _hash_token_legacy(token: str) -> str:
    """Legacy plain SHA256 hash -- used only for backwards-compatible lookups."""
    return hashlib.sha256(token.encode()).hexdigest()


class InvitationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def _find_invitation(
        self, raw_token: str, now: datetime,
    ) -> tuple[Invitation | None, bool]:
        """Look up invitation by token hash. Tries HMAC first, falls back to legacy SHA256.

        Returns (invitation, needs_migration).
        """
        for hash_fn, is_legacy in ((hmac_hash, False), (_hash_token_legacy, True)):
            token_hash = hash_fn(raw_token)
            result = await self.db.execute(
                select(Invitation).where(
                    Invitation.token_hash == token_hash,
                    Invitation.revoked.is_(False),
                    Invitation.accepted_at.is_(None),
                    Invitation.expires_at > now,
                )
            )
            invitation = result.scalar_one_or_none()
            if invitation:
                return invitation, is_legacy
        return None, False

    async def create_invitation(
        self,
        tenant_id: uuid.UUID,
        email: str,
        inviter: User,
        group_id: uuid.UUID | None = None,
        invitation_type: str = "membership",
    ) -> tuple[Invitation, str]:
        """Create an invitation. Returns (invitation, raw_token)."""
        # Validate group_id if provided
        group = None
        if group_id:
            result = await self.db.execute(
                select(PermissionGroup).where(
                    PermissionGroup.id == group_id,
                    PermissionGroup.tenant_id == tenant_id,
                )
            )
            group = result.scalar_one_or_none()
            if not group:
                raise NotFoundError("PermissionGroup", str(group_id))

        # Check: email not already a member of this tenant
        existing_member = await self.db.execute(
            select(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .where(
                User.email == email,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active,
            )
        )
        if existing_member.scalar_one_or_none():
            raise ConflictError(f"Gebruiker '{email}' is al lid van deze organisatie")

        # Check: invitee is not a platform user
        target_user = await self.db.execute(select(User).where(User.email == email))
        target = target_user.scalar_one_or_none()
        if target and await is_platform_user(target.id, self.db):
            await self.audit.log(
                "platform_user.invite_blocked",
                user_id=inviter.id,
                target_email=email,
                tenant_id=str(tenant_id),
            )
            raise ForbiddenError(
                "Platformgebruikers kunnen niet worden uitgenodigd voor een organisatie"
            )

        # Check: no pending invite for same email + tenant
        now = datetime.now(timezone.utc)
        existing_invite = await self.db.execute(
            select(Invitation).where(
                Invitation.email == email,
                Invitation.tenant_id == tenant_id,
                Invitation.revoked.is_(False),
                Invitation.accepted_at.is_(None),
                Invitation.expires_at > now,
            )
        )
        if existing_invite.scalar_one_or_none():
            raise ConflictError(f"Er staat al een uitnodiging open voor '{email}'")

        # Generate token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hmac_hash(raw_token)
        expires_at = now + timedelta(hours=settings.invitation_expire_hours)

        invitation = Invitation(
            tenant_id=tenant_id,
            email=email,
            group_id=group_id,
            token_hash=token_hash,
            expires_at=expires_at,
            invited_by_id=inviter.id,
            invitation_type=invitation_type,
        )
        self.db.add(invitation)
        await self.db.flush()

        # Get tenant name for email
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one()

        # Send invitation email
        accept_url = f"{settings.frontend_url}/auth/accept-invite?token={raw_token}"
        role_label = group.name if group else "lid"
        subject, html = build_invitation_email(
            inviter_name=inviter.full_name,
            org_name=tenant.name,
            role=role_label,
            accept_url=accept_url,
            expire_hours=settings.invitation_expire_hours,
        )
        await send_email_safe(email, subject, html, sender=EmailSender.ACCOUNT)

        await self.audit.log(
            "invitation.created",
            user_id=inviter.id,
            email=email,
            tenant_id=str(tenant_id),
        )

        logger.info("invitation.created", email=email, tenant_id=str(tenant_id))
        return invitation, raw_token

    async def list_pending(self, tenant_id: uuid.UUID) -> list[InvitationResponse]:
        """List pending invitations for a tenant."""

        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Invitation, User.full_name)
            .join(User, User.id == Invitation.invited_by_id)
            .outerjoin(PermissionGroup, PermissionGroup.id == Invitation.group_id)
            .add_columns(PermissionGroup.name.label("group_name"))
            .where(
                Invitation.tenant_id == tenant_id,
                Invitation.revoked.is_(False),
                Invitation.accepted_at.is_(None),
                Invitation.expires_at > now,
            )
            .order_by(Invitation.created_at.desc())
        )
        items = []
        for inv, inviter_name, group_name in result.all():
            items.append(
                InvitationResponse(
                    id=inv.id,
                    email=inv.email,
                    group_id=inv.group_id,
                    group_name=group_name,
                    tenant_id=inv.tenant_id,
                    invited_by_name=inviter_name,
                    expires_at=inv.expires_at,
                    created_at=inv.created_at,
                )
            )
        return items

    async def list_invitations(
        self, tenant_id: uuid.UUID, status: str | None = None
    ) -> list[InvitationWithStatus]:
        """List invitations for a tenant with optional status filter."""
        now = datetime.now(timezone.utc)

        query = (
            select(Invitation, User.full_name)
            .join(User, User.id == Invitation.invited_by_id)
            .outerjoin(PermissionGroup, PermissionGroup.id == Invitation.group_id)
            .add_columns(PermissionGroup.name.label("group_name"))
            .where(Invitation.tenant_id == tenant_id)
        )

        if status == "pending":
            query = query.where(
                Invitation.revoked.is_(False),
                Invitation.accepted_at.is_(None),
                Invitation.expires_at > now,
            )
        elif status == "accepted":
            query = query.where(Invitation.accepted_at.is_not(None))
        elif status == "revoked":
            query = query.where(Invitation.revoked)
        elif status == "expired":
            query = query.where(
                Invitation.revoked.is_(False),
                Invitation.accepted_at.is_(None),
                Invitation.expires_at <= now,
            )

        query = query.order_by(Invitation.created_at.desc())
        result = await self.db.execute(query)

        items = []
        for inv, inviter_name, group_name in result.all():
            # Determine status
            if inv.accepted_at is not None:
                inv_status = "accepted"
            elif inv.revoked:
                inv_status = "revoked"
            elif inv.expires_at <= now:
                inv_status = "expired"
            else:
                inv_status = "pending"

            items.append(
                InvitationWithStatus(
                    id=inv.id,
                    email=inv.email,
                    group_id=inv.group_id,
                    group_name=group_name,
                    tenant_id=inv.tenant_id,
                    invited_by_name=inviter_name,
                    expires_at=inv.expires_at,
                    created_at=inv.created_at,
                    status=inv_status,
                    accepted_at=inv.accepted_at,
                )
            )
        return items

    async def create_bulk_invitations(
        self,
        tenant_id: uuid.UUID,
        emails: list[str],
        inviter: User,
        group_id: uuid.UUID | None = None,
    ) -> BulkInvitationResponse:
        """Create invitations for multiple emails. Continues on individual failures."""
        results: list[BulkInvitationResult] = []
        created = 0
        failed = 0

        # Pre-fetch group name to avoid lazy loading
        group_name = None
        if group_id:
            g_result = await self.db.execute(
                select(PermissionGroup.name).where(PermissionGroup.id == group_id)
            )
            group_name = g_result.scalar_one_or_none()

        for email in emails:
            try:
                invitation, _ = await self.create_invitation(
                    tenant_id, email, inviter, group_id=group_id
                )
                results.append(
                    BulkInvitationResult(
                        email=email,
                        success=True,
                        invitation=InvitationResponse(
                            id=invitation.id,
                            email=invitation.email,
                            group_id=invitation.group_id,
                            group_name=group_name,
                            tenant_id=invitation.tenant_id,
                            invited_by_name=inviter.full_name,
                            expires_at=invitation.expires_at,
                            created_at=invitation.created_at,
                        ),
                    )
                )
                created += 1
            except (ConflictError, NotFoundError, ForbiddenError) as e:
                results.append(
                    BulkInvitationResult(email=email, success=False, error=str(e))
                )
                failed += 1

        return BulkInvitationResponse(created=created, failed=failed, results=results)

    async def resend_invitation(
        self, invitation_id: uuid.UUID, tenant_id: uuid.UUID, inviter: User
    ) -> None:
        """Resend invitation with a new token and reset expiry."""
        result = await self.db.execute(
            select(Invitation).where(
                Invitation.id == invitation_id,
                Invitation.tenant_id == tenant_id,
                Invitation.revoked.is_(False),
                Invitation.accepted_at.is_(None),
            )
        )
        invitation = result.scalar_one_or_none()
        if not invitation:
            raise NotFoundError("Invitation", str(invitation_id))

        # Generate new token
        raw_token = secrets.token_urlsafe(32)
        invitation.token_hash = hmac_hash(raw_token)
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.invitation_expire_hours
        )
        await self.db.flush()

        # Get tenant
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one()

        # Resend email
        accept_url = f"{settings.frontend_url}/auth/accept-invite?token={raw_token}"
        # Get group name for label
        role_label = "lid"
        if invitation.group_id:
            group_result = await self.db.execute(
                select(PermissionGroup.name).where(PermissionGroup.id == invitation.group_id)
            )
            gname = group_result.scalar_one_or_none()
            if gname:
                role_label = gname
        subject, html = build_invitation_email(
            inviter_name=inviter.full_name,
            org_name=tenant.name,
            role=role_label,
            accept_url=accept_url,
            expire_hours=settings.invitation_expire_hours,
        )
        await send_email_safe(invitation.email, subject, html, sender=EmailSender.ACCOUNT)

        logger.info("invitation.resent", invitation_id=str(invitation_id))

    async def revoke_invitation(
        self, invitation_id: uuid.UUID, tenant_id: uuid.UUID, revoker: User
    ) -> None:
        """Revoke a pending invitation."""
        result = await self.db.execute(
            select(Invitation).where(
                Invitation.id == invitation_id,
                Invitation.tenant_id == tenant_id,
                Invitation.revoked.is_(False),
                Invitation.accepted_at.is_(None),
            )
        )
        invitation = result.scalar_one_or_none()
        if not invitation:
            raise NotFoundError("Invitation", str(invitation_id))

        invitation.revoked = True
        await self.db.flush()

        await self.audit.log(
            "invitation.revoked",
            user_id=revoker.id,
            invitation_id=str(invitation_id),
        )
        logger.info("invitation.revoked", invitation_id=str(invitation_id))

    async def _get_or_create_nieuw_group(self) -> PermissionGroup:
        """Get the 'nieuw' platform landing group, creating it on-demand if needed."""
        result = await self.db.execute(
            select(PermissionGroup).where(
                PermissionGroup.tenant_id.is_(None),
                PermissionGroup.slug == "nieuw",
            )
        )
        group = result.scalar_one_or_none()
        if group:
            return group

        # On-demand creation (mirrors create_default_platform_groups logic)
        group = PermissionGroup(
            tenant_id=None,
            name="Nieuw",
            slug="nieuw",
            description="Landing-groep voor uitgenodigde platformgebruikers (geen rechten)",
            is_default=True,
        )
        self.db.add(group)
        await self.db.flush()
        # No permissions — intentionally empty
        return group

    async def create_platform_invitation(
        self,
        email: str,
        inviter: User,
    ) -> dict[str, str]:
        """Create a platform-level invitation. Always sends an invitation link."""
        from app.core.email import build_platform_invite_email

        # Check: email already a platform user?
        target_result = await self.db.execute(select(User).where(User.email == email))
        target = target_result.scalar_one_or_none()
        if target and await is_platform_user(target.id, self.db):
            raise ConflictError("Al een platformgebruiker")

        # Check: duplicate pending platform invite?
        now = datetime.now(timezone.utc)
        existing_invite = await self.db.execute(
            select(Invitation).where(
                Invitation.email == email,
                Invitation.tenant_id.is_(None),
                Invitation.invitation_type == "platform",
                Invitation.revoked.is_(False),
                Invitation.accepted_at.is_(None),
                Invitation.expires_at > now,
            )
        )
        if existing_invite.scalar_one_or_none():
            raise ConflictError("Er staat al een uitnodiging open voor dit emailadres")

        # Get or create "nieuw" landing group
        nieuw_group = await self._get_or_create_nieuw_group()

        # Generate token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hmac_hash(raw_token)
        expires_at = now + timedelta(hours=settings.invitation_expire_hours)

        invitation = Invitation(
            tenant_id=None,
            email=email,
            group_id=nieuw_group.id,
            token_hash=token_hash,
            expires_at=expires_at,
            invited_by_id=inviter.id,
            invitation_type="platform",
        )
        self.db.add(invitation)
        await self.db.flush()

        # Send invitation email
        accept_url = f"{settings.frontend_url}/auth/accept-invite?token={raw_token}"
        subject, html = build_platform_invite_email(
            inviter_name=inviter.full_name,
            accept_url=accept_url,
            expire_hours=settings.invitation_expire_hours,
        )
        await send_email_safe(email, subject, html, sender=EmailSender.ACCOUNT)

        await self.audit.log(
            "platform_invitation.created",
            user_id=inviter.id,
            email=email,
        )

        logger.info("platform_invitation.created", email=email)
        return {"message": "Uitnodiging is verstuurd"}

    async def get_invite_info(
        self,
        token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> InviteInfo:
        """Get information about an invitation from its token (public endpoint)."""
        now = datetime.now(timezone.utc)
        invitation, needs_migration = await self._find_invitation(token, now)
        if not invitation:
            raise AuthenticationError("Ongeldige of verlopen uitnodiging")

        # Auto-migrate legacy SHA256 hash to HMAC
        if needs_migration:
            invitation.token_hash = hmac_hash(token)
            await self.db.flush()

        # Get tenant name (conditional — NULL for platform invites)
        org_name = None
        if invitation.tenant_id is not None:
            tenant_result = await self.db.execute(
                select(Tenant).where(Tenant.id == invitation.tenant_id)
            )
            tenant = tenant_result.scalar_one()
            org_name = tenant.name

        # Get inviter name
        inviter_result = await self.db.execute(
            select(User).where(User.id == invitation.invited_by_id)
        )
        inviter = inviter_result.scalar_one()

        # Check if user already exists
        existing_user = await self.db.execute(
            select(User).where(User.email == invitation.email)
        )
        is_existing = existing_user.scalar_one_or_none() is not None

        # Get group name if applicable
        group_name = None
        if invitation.group_id:
            group_result = await self.db.execute(
                select(PermissionGroup.name).where(PermissionGroup.id == invitation.group_id)
            )
            group_name = group_result.scalar_one_or_none()

        # Audit log: track who views invitation info (IP + UA for anomaly detection)
        await self.audit.log(
            "invitation.info_viewed",
            ip_address=ip_address,
            user_agent=user_agent,
            email=invitation.email,
            tenant_id=str(invitation.tenant_id) if invitation.tenant_id else None,
        )

        return InviteInfo(
            org_name=org_name,
            group_name=group_name,
            email=invitation.email,
            inviter_name=inviter.full_name,
            is_existing_user=is_existing,
            invitation_type=invitation.invitation_type,
        )

    async def accept_invitation(
        self,
        token: str,
        password: str | None = None,
        full_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        current_user: User | None = None,
    ) -> AcceptInvitationResponse:
        """Accept an invitation. Creates user if needed, adds membership."""
        now = datetime.now(timezone.utc)
        invitation, needs_migration = await self._find_invitation(token, now)
        if not invitation:
            raise AuthenticationError("Ongeldige of verlopen uitnodiging")

        # Auto-migrate legacy hash + invalidate token FIRST (prevent replay on crash)
        if needs_migration:
            invitation.token_hash = hmac_hash(token)
        invitation.accepted_at = now
        await self.db.flush()

        # Check if user exists
        user_result = await self.db.execute(
            select(User).where(User.email == invitation.email)
        )
        user = user_result.scalar_one_or_none()
        is_new_user = user is None

        # --- Platform invitation branch ---
        if invitation.invitation_type == "platform":
            if is_new_user:
                if not password or not full_name:
                    raise AuthenticationError(
                        "Wachtwoord en naam zijn verplicht voor nieuwe gebruikers"
                    )
                user = User(
                    email=invitation.email,
                    hashed_password=hash_password(password),
                    full_name=full_name,
                    email_verified=True,
                )
                self.db.add(user)
                await self.db.flush()
            else:
                # Existing user: require authentication and email match
                if not current_user:
                    raise AuthenticationError(
                        "Je moet ingelogd zijn om deze uitnodiging te accepteren"
                    )
                if current_user.email != invitation.email:
                    raise ForbiddenError(
                        "Je bent ingelogd met een ander account dan waarvoor de uitnodiging is"
                    )

            # Group assignment (no TenantMembership for platform invites)
            if invitation.group_id:
                assignment = UserGroupAssignment(
                    user_id=user.id,
                    group_id=invitation.group_id,
                )
                self.db.add(assignment)

            await self.audit.log(
                "platform_invitation.accepted",
                user_id=user.id,
                email=invitation.email,
                is_new_user=is_new_user,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            logger.info(
                "platform_invitation.accepted",
                user_id=str(user.id),
                is_new_user=is_new_user,
            )

            return AcceptInvitationResponse(
                message="Uitnodiging geaccepteerd!",
                is_new_user=is_new_user,
                tenant_name=None,
            )

        # --- Org invitation branch (existing flow) ---

        # Get tenant
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == invitation.tenant_id)
        )
        tenant = tenant_result.scalar_one()

        # Block platform users from accepting org invitations
        if user and not is_new_user and await is_platform_user(user.id, self.db):
            await self.audit.log(
                "platform_user.accept_blocked",
                user_id=user.id,
                tenant_id=str(invitation.tenant_id),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise ForbiddenError(
                "Platformgebruikers kunnen geen lidmaatschap accepteren"
            )

        if is_new_user:
            if not password or not full_name:
                raise AuthenticationError(
                    "Wachtwoord en naam zijn verplicht voor nieuwe gebruikers"
                )
            user = User(
                email=invitation.email,
                hashed_password=hash_password(password),
                full_name=full_name,
                email_verified=True,  # Verified via invitation link
            )
            self.db.add(user)
            await self.db.flush()

        # Create membership
        membership_type = "collaboration" if invitation.invitation_type == "collaboration" else "full"
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=invitation.tenant_id,
            membership_type=membership_type,
        )
        self.db.add(membership)
        await self.db.flush()

        # Create group assignment if invitation has a group_id
        if invitation.group_id:
            assignment = UserGroupAssignment(
                user_id=user.id,
                group_id=invitation.group_id,
            )
            self.db.add(assignment)

        await self.audit.log(
            "invitation.accepted",
            user_id=user.id,
            email=invitation.email,
            tenant_id=str(invitation.tenant_id),
            is_new_user=is_new_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "invitation.accepted",
            user_id=str(user.id),
            tenant_id=str(invitation.tenant_id),
            is_new_user=is_new_user,
        )

        return AcceptInvitationResponse(
            message="Uitnodiging geaccepteerd!",
            is_new_user=is_new_user,
            tenant_name=tenant.name,
        )

