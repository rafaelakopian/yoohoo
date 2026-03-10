"""Operations service — orchestrates central DB queries and cross-tenant metrics.

Dashboard cache is per-process (in-memory, 15s TTL). When running multiple API replicas,
each worker has its own cache — cached_at may differ slightly between workers. This is
fine for monitoring purposes.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings as app_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import create_impersonation_token, verify_password
from app.db.tenant import TenantDatabaseManager, tenant_db_manager
from app.modules.platform.auth.models import (
    AuditLog,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.operations.metrics import TenantMetricsCollector
from app.modules.platform.operations.models import SupportNote
from app.modules.platform.operations.schemas import (
    AuditEvent,
    ImpersonateResponse,
    InvoiceStats,
    OnboardingItem,
    SupportNoteCreate,
    SupportNoteResponse,
    SupportNoteUpdate,
    Tenant360Detail,
    Tenant360Member,
    TenantHealthDashboard,
    TenantHealthItem,
    TenantSettingsSummary,
    TimelineEvent,
    TimelineResponse,
)
from app.modules.platform.tenant_mgmt.models import Tenant

logger = structlog.get_logger()

# Per-process dashboard cache (15s TTL)
_dashboard_cache: dict = {"data": None, "cached_at": None}
_CACHE_TTL = 15  # seconds

# Semaphore for cross-tenant queries (limit concurrent DB connections)
_TENANT_QUERY_SEM = asyncio.Semaphore(5)

# Timeout for individual tenant queries (seconds)
_TENANT_QUERY_TIMEOUT = 2.0


class OperationsService:
    def __init__(self, db: AsyncSession, db_manager: TenantDatabaseManager | None = None):
        self.db = db
        self.metrics = TenantMetricsCollector(db_manager or tenant_db_manager)

    # ------------------------------------------------------------------
    # A1: Tenant Health Dashboard
    # ------------------------------------------------------------------

    async def get_tenant_health_dashboard(self) -> TenantHealthDashboard:
        """All tenants overview with product metrics. Cached for 15s."""
        now = datetime.now(timezone.utc)
        cached_at = _dashboard_cache.get("cached_at")
        if (
            _dashboard_cache.get("data") is not None
            and cached_at is not None
            and (now - cached_at).total_seconds() < _CACHE_TTL
        ):
            return _dashboard_cache["data"]

        result = await self._build_dashboard()
        _dashboard_cache["data"] = result
        _dashboard_cache["cached_at"] = now
        return result

    async def _build_dashboard(self) -> TenantHealthDashboard:
        """Fresh dashboard query — central DB + cross-tenant metrics."""
        # Platform stats
        stats = await self._get_platform_stats()

        # Tenant list with members
        tenants = await self._get_all_tenants_with_members()

        # Cross-tenant metrics for provisioned tenants
        provisioned_slugs = [t for t in tenants if t["is_provisioned"]]
        metrics_map = await self._query_provisioned_tenants(
            self.metrics.collect_counts,
            [t["slug"] for t in provisioned_slugs],
        )

        # Last activity per tenant (from audit log)
        activity_map = await self._get_last_activity_per_tenant()

        # Build items
        items = []
        for t in tenants:
            metrics = metrics_map.get(t["slug"], {})
            items.append(TenantHealthItem(
                id=t["id"],
                name=t["name"],
                slug=t["slug"],
                is_active=t["is_active"],
                is_provisioned=t["is_provisioned"],
                owner_name=t["owner_name"],
                member_count=t["member_count"],
                created_at=t["created_at"],
                metrics_available=metrics.get("metrics_available", False),
                student_count=metrics.get("student_count", 0),
                teacher_count=metrics.get("teacher_count", 0),
                active_invoice_count=metrics.get("active_invoice_count", 0),
                last_activity_at=activity_map.get(t["id"]),
            ))

        return TenantHealthDashboard(
            total_tenants=stats["total_tenants"],
            active_tenants=stats["active_tenants"],
            provisioned_tenants=stats["provisioned_tenants"],
            total_users=stats["total_users"],
            active_users=stats["active_users"],
            tenants=items,
            cached_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # A2: Tenant 360° Detail
    # ------------------------------------------------------------------

    async def get_tenant_360(self, tenant_id: uuid.UUID) -> Tenant360Detail:
        """Complete overview of a single tenant."""
        result = await self.db.execute(
            select(Tenant)
            .options(
                selectinload(Tenant.memberships).selectinload(TenantMembership.user),
                selectinload(Tenant.settings),
            )
            .where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundError("Tenant", str(tenant_id))

        # Owner name
        owner_name = None
        if tenant.owner_id:
            owner = (await self.db.execute(
                select(User.full_name).where(User.id == tenant.owner_id)
            )).scalar_one_or_none()
            owner_name = owner

        # Settings summary (typed, no raw dict)
        settings = None
        if tenant.settings:
            settings = TenantSettingsSummary(
                org_name=tenant.settings.org_name,
                org_email=tenant.settings.org_email,
                org_phone=tenant.settings.org_phone,
                timezone=tenant.settings.timezone,
            )

        # Group assignments for members
        group_result = await self.db.execute(
            select(UserGroupAssignment)
            .join(PermissionGroup)
            .options(selectinload(UserGroupAssignment.group))
            .where(PermissionGroup.tenant_id == tenant_id)
        )
        user_groups: dict[uuid.UUID, list[str]] = {}
        for a in group_result.scalars().all():
            user_groups.setdefault(a.user_id, []).append(a.group.name)

        # Members (all with active membership)
        members = [
            Tenant360Member(
                user_id=m.user_id,
                email=m.user.email,
                full_name=m.user.full_name,
                is_active=m.is_active,
                is_superadmin=m.user.is_superadmin,
                groups=user_groups.get(m.user_id, []),
                last_login_at=m.user.last_login_at,
            )
            for m in tenant.memberships
        ]

        # Product metrics (from tenant DB)
        metrics = {}
        if tenant.is_provisioned:
            try:
                metrics = await asyncio.wait_for(
                    self.metrics.collect_full(tenant.slug),
                    timeout=_TENANT_QUERY_TIMEOUT,
                )
                metrics["metrics_available"] = True
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("operations.tenant_360_metrics_failed",
                               slug=tenant.slug, error=str(e))
                metrics = {"metrics_available": False}

        # Recent audit events (sanitized)
        recent_events = await self._get_tenant_events(tenant_id, limit=20)

        # Last activity
        last_activity = recent_events[0].created_at if recent_events else None

        # Build invoice stats
        inv = metrics.get("invoice_stats", {})
        invoice_stats = InvoiceStats(
            sent_count=inv.get("sent_count", 0),
            paid_count=inv.get("paid_count", 0),
            overdue_count=inv.get("overdue_count", 0),
            total_outstanding_cents=inv.get("total_outstanding_cents", 0),
            total_paid_cents=inv.get("total_paid_cents", 0),
        )

        return Tenant360Detail(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            is_provisioned=tenant.is_provisioned,
            owner_name=owner_name,
            created_at=tenant.created_at,
            settings=settings,
            members=members,
            metrics_available=metrics.get("metrics_available", False),
            student_count=metrics.get("student_count", 0),
            active_student_count=metrics.get("active_student_count", 0),
            teacher_count=metrics.get("teacher_count", 0),
            lesson_slot_count=metrics.get("lesson_slot_count", 0),
            attendance_present_count=metrics.get("attendance_present_count", 0),
            attendance_total_count=metrics.get("attendance_total_count", 0),
            invoice_stats=invoice_stats,
            last_activity_at=last_activity,
            recent_events=recent_events,
        )

    # ------------------------------------------------------------------
    # A4: Onboarding Overview
    # ------------------------------------------------------------------

    async def get_onboarding_overview(self) -> list[OnboardingItem]:
        """All tenants with onboarding checklist."""
        tenants = await self._get_all_tenants_with_members()

        # Cross-tenant onboarding checks
        provisioned_slugs = [t["slug"] for t in tenants if t["is_provisioned"]]
        onboarding_map = await self._query_provisioned_tenants(
            self.metrics.collect_onboarding,
            provisioned_slugs,
        )

        items = []
        for t in tenants:
            onb = onboarding_map.get(t["slug"], {})
            has_settings = bool(t.get("settings_org_name"))
            has_members = t["member_count"] >= 2  # owner + at least 1 invited

            checks = {
                "is_provisioned": t["is_provisioned"],
                "has_settings": has_settings,
                "has_members": has_members,
                "has_students": onb.get("has_students", False),
                "has_schedule": onb.get("has_schedule", False),
                "has_attendance": onb.get("has_attendance", False),
                "has_billing_plan": onb.get("has_billing_plan", False),
            }

            pct, missing = self._calculate_onboarding(checks)

            items.append(OnboardingItem(
                tenant_id=t["id"],
                tenant_name=t["name"],
                tenant_slug=t["slug"],
                created_at=t["created_at"],
                **checks,
                completion_pct=pct,
                missing_steps=missing,
                last_step_at=onb.get("last_step_at"),
            ))

        return items

    # ------------------------------------------------------------------
    # Audit Events (for Tenant 360)
    # ------------------------------------------------------------------

    async def get_tenant_events(
        self, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0,
    ) -> list[AuditEvent]:
        """Paginated audit events for a tenant (sanitized)."""
        # Verify tenant exists
        exists = (await self.db.execute(
            select(Tenant.id).where(Tenant.id == tenant_id)
        )).scalar_one_or_none()
        if not exists:
            raise NotFoundError("Tenant", str(tenant_id))

        return await self._get_tenant_events(tenant_id, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_platform_stats(self) -> dict:
        tenant_counts = await self.db.execute(
            select(
                func.count(Tenant.id).label("total"),
                func.count(Tenant.id).filter(Tenant.is_active).label("active"),
                func.count(Tenant.id).filter(Tenant.is_provisioned).label("provisioned"),
            )
        )
        row = tenant_counts.one()

        user_counts = await self.db.execute(
            select(
                func.count(User.id).label("total"),
                func.count(User.id).filter(User.is_active).label("active"),
            )
        )
        urow = user_counts.one()

        return {
            "total_tenants": row.total,
            "active_tenants": row.active,
            "provisioned_tenants": row.provisioned,
            "total_users": urow.total,
            "active_users": urow.active,
        }

    async def _get_all_tenants_with_members(self) -> list[dict]:
        """All tenants with owner name and member count."""
        result = await self.db.execute(
            select(Tenant)
            .options(
                selectinload(Tenant.memberships).selectinload(TenantMembership.user),
                selectinload(Tenant.settings),
            )
            .order_by(Tenant.name)
        )
        tenants = result.scalars().all()

        items = []
        for t in tenants:
            owner_name = None
            if t.owner_id:
                owner = (await self.db.execute(
                    select(User.full_name).where(User.id == t.owner_id)
                )).scalar_one_or_none()
                owner_name = owner

            real_members = [m for m in t.memberships if not m.user.is_superadmin]

            items.append({
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "is_active": t.is_active,
                "is_provisioned": t.is_provisioned,
                "owner_name": owner_name,
                "member_count": len(real_members),
                "created_at": t.created_at,
                "settings_org_name": t.settings.org_name if t.settings else None,
            })

        return items

    async def _get_last_activity_per_tenant(self) -> dict[uuid.UUID, datetime]:
        """Last audit log entry per tenant_id."""
        result = await self.db.execute(
            select(
                AuditLog.tenant_id,
                func.max(AuditLog.created_at).label("last_at"),
            )
            .where(AuditLog.tenant_id.is_not(None))
            .group_by(AuditLog.tenant_id)
        )
        return {row.tenant_id: row.last_at for row in result.all()}

    async def _get_tenant_events(
        self, tenant_id: uuid.UUID, limit: int = 20, offset: int = 0,
    ) -> list[AuditEvent]:
        """Sanitized audit events for a tenant — no raw details/payload."""
        result = await self.db.execute(
            select(
                AuditLog.action,
                AuditLog.ip_address,
                AuditLog.created_at,
                User.email.label("user_email"),
            )
            .outerjoin(User, AuditLog.user_id == User.id)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        return [
            AuditEvent(
                action=row.action,
                user_email=row.user_email,
                ip_address=row.ip_address,
                created_at=row.created_at,
            )
            for row in result.all()
        ]

    async def _query_provisioned_tenants(
        self, collector_fn, slugs: list[str],
    ) -> dict[str, dict]:
        """Query all provisioned tenants in parallel with semaphore + timeout.

        Timeout is applied here only (not in collector) for a single control point.
        """
        async def safe_query(slug: str) -> tuple[str, dict]:
            async with _TENANT_QUERY_SEM:
                try:
                    data = await asyncio.wait_for(
                        collector_fn(slug), timeout=_TENANT_QUERY_TIMEOUT,
                    )
                    data["metrics_available"] = True
                    return (slug, data)
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(
                        "operations.tenant_query_failed",
                        slug=slug, error=str(e),
                    )
                    return (slug, {"metrics_available": False})

        results = await asyncio.gather(*[safe_query(s) for s in slugs])
        return dict(results)

    @staticmethod
    def _calculate_onboarding(checks: dict) -> tuple[int, list[str]]:
        """Calculate onboarding completion percentage and missing steps."""
        steps = [
            "is_provisioned", "has_settings", "has_members", "has_students",
            "has_schedule", "has_attendance", "has_billing_plan",
        ]
        missing = [s for s in steps if not checks.get(s)]
        pct = int((len(steps) - len(missing)) / len(steps) * 100)
        return pct, missing

    # ------------------------------------------------------------------
    # B4: Support Notes
    # ------------------------------------------------------------------

    def _note_to_response(self, note: SupportNote) -> SupportNoteResponse:
        """Convert a SupportNote ORM object to a response schema."""
        return SupportNoteResponse(
            id=note.id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_by_id=note.created_by_id,
            created_by_name=note.created_by.full_name if note.created_by else "Onbekend",
            created_by_email=note.created_by.email if note.created_by else "",
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    async def _list_notes(
        self, *, tenant_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None,
    ) -> list[SupportNoteResponse]:
        """List notes for a tenant or user. Pinned first, then newest."""
        query = (
            select(SupportNote)
            .where(SupportNote.deleted_at.is_(None))
            .order_by(SupportNote.is_pinned.desc(), SupportNote.created_at.desc())
        )
        if tenant_id:
            query = query.where(SupportNote.tenant_id == tenant_id)
        elif user_id:
            query = query.where(SupportNote.user_id == user_id)

        result = await self.db.execute(query)
        return [self._note_to_response(n) for n in result.scalars().all()]

    async def list_tenant_notes(self, tenant_id: uuid.UUID) -> list[SupportNoteResponse]:
        return await self._list_notes(tenant_id=tenant_id)

    async def list_user_notes(self, user_id: uuid.UUID) -> list[SupportNoteResponse]:
        return await self._list_notes(user_id=user_id)

    async def create_tenant_note(
        self, tenant_id: uuid.UUID, author: User, data: SupportNoteCreate,
    ) -> SupportNoteResponse:
        note = SupportNote(
            tenant_id=tenant_id,
            content=data.content,
            is_pinned=data.is_pinned,
            created_by_id=author.id,
        )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note, ["created_by"])
        return self._note_to_response(note)

    async def create_user_note(
        self, user_id: uuid.UUID, author: User, data: SupportNoteCreate,
    ) -> SupportNoteResponse:
        note = SupportNote(
            user_id=user_id,
            content=data.content,
            is_pinned=data.is_pinned,
            created_by_id=author.id,
        )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note, ["created_by"])
        return self._note_to_response(note)

    async def _get_note_or_404(self, note_id: uuid.UUID) -> SupportNote:
        result = await self.db.execute(
            select(SupportNote).where(
                SupportNote.id == note_id,
                SupportNote.deleted_at.is_(None),
            )
        )
        note = result.scalar_one_or_none()
        if not note:
            raise NotFoundError("SupportNote", str(note_id))
        return note

    async def update_note(
        self, note_id: uuid.UUID, author: User, data: SupportNoteUpdate,
    ) -> SupportNoteResponse:
        note = await self._get_note_or_404(note_id)
        if note.created_by_id != author.id and not author.is_superadmin:
            raise ForbiddenError("Je kunt alleen je eigen notities bewerken.")
        if data.content is not None:
            note.content = data.content
        if data.is_pinned is not None:
            note.is_pinned = data.is_pinned
        note.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(note, ["created_by"])
        return self._note_to_response(note)

    async def delete_note(self, note_id: uuid.UUID, author: User) -> None:
        note = await self._get_note_or_404(note_id)
        if note.created_by_id != author.id and not author.is_superadmin:
            raise ForbiddenError("Je kunt alleen je eigen notities verwijderen.")
        note.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def toggle_pin_note(
        self, note_id: uuid.UUID, author: User,
    ) -> SupportNoteResponse:
        note = await self._get_note_or_404(note_id)
        note.is_pinned = not note.is_pinned
        note.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(note, ["created_by"])
        return self._note_to_response(note)

    # ------------------------------------------------------------------
    # B2: Quick Actions
    # ------------------------------------------------------------------

    async def _get_target_user(self, user_id: uuid.UUID) -> User:
        """Fetch target user and validate it's not a superadmin."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))
        if user.is_superadmin:
            raise ForbiddenError("Acties op superadmin-accounts zijn niet toegestaan.")
        return user

    def _verify_admin_password(self, admin: User, password: str) -> None:
        """Verify admin's own password for sensitive actions."""
        if not verify_password(password, admin.hashed_password):
            raise ForbiddenError("Ongeldig wachtwoord.")

    async def _check_cooldown(
        self, action: str, target_id: uuid.UUID, seconds: int = 60,
    ) -> None:
        """Check if an action was performed recently on target (cooldown)."""
        from app.modules.platform.auth.models import AuditLog as AL
        cutoff = datetime.now(timezone.utc).replace(
            second=datetime.now(timezone.utc).second,
        )
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)

        count = (await self.db.execute(
            select(func.count(AL.id)).where(
                AL.action == action,
                AL.details["target_user_id"].as_string() == str(target_id),
                AL.created_at > cutoff,
            )
        )).scalar() or 0
        if count > 0:
            raise ConflictError(
                f"Deze actie is recent al uitgevoerd. Wacht {seconds} seconden.",
            )

    async def force_password_reset(
        self, admin: User, target_user_id: uuid.UUID,
        ip: str | None = None, ua: str | None = None,
    ) -> None:
        """Send password reset email for target user."""
        target = await self._get_target_user(target_user_id)
        await self._check_cooldown("operations.force_password_reset", target_user_id)

        from app.modules.platform.auth.password.service import PasswordService
        pwd_service = PasswordService(self.db)
        await pwd_service.request_password_reset(target.email, ip_address=ip, user_agent=ua)

        from app.modules.platform.auth.audit import AuditService
        audit = AuditService(self.db)
        await audit.log(
            "operations.force_password_reset",
            user_id=admin.id,
            ip_address=ip,
            user_agent=ua,
            target_user_id=str(target_user_id),
            target_email=target.email,
        )

    async def toggle_user_active(
        self, admin: User, target_user_id: uuid.UUID, admin_password: str,
        ip: str | None = None, ua: str | None = None,
    ) -> dict:
        """Activate or deactivate a user account. Requires admin password."""
        self._verify_admin_password(admin, admin_password)
        target = await self._get_target_user(target_user_id)

        if target_user_id == admin.id:
            raise ForbiddenError("Je kunt jezelf niet deactiveren.")

        new_active = not target.is_active
        target.is_active = new_active

        # Revoke all sessions on deactivation
        revoked = 0
        if not new_active:
            from app.modules.platform.auth.session.service import SessionService
            session_svc = SessionService(self.db)
            revoked = await session_svc.revoke_all_sessions(
                target_user_id, ip_address=ip, user_agent=ua,
            )

        await self.db.flush()

        action = "operations.user_activated" if new_active else "operations.user_deactivated"
        from app.modules.platform.auth.audit import AuditService
        audit = AuditService(self.db)
        await audit.log(
            action,
            user_id=admin.id,
            ip_address=ip,
            user_agent=ua,
            target_user_id=str(target_user_id),
            target_email=target.email,
            sessions_revoked=revoked,
        )

        return {"is_active": new_active}

    async def resend_verification_email(
        self, admin: User, target_user_id: uuid.UUID,
        ip: str | None = None, ua: str | None = None,
    ) -> None:
        """Resend email verification for unverified user."""
        target = await self._get_target_user(target_user_id)
        if target.email_verified:
            raise ConflictError("Gebruiker is al geverifieerd.")

        from app.modules.platform.auth.core.service import AuthService
        auth_svc = AuthService(self.db)
        await auth_svc.resend_verification(target.email)

        from app.modules.platform.auth.audit import AuditService
        audit = AuditService(self.db)
        await audit.log(
            "operations.resend_verification",
            user_id=admin.id,
            ip_address=ip,
            user_agent=ua,
            target_user_id=str(target_user_id),
            target_email=target.email,
        )

    async def revoke_user_sessions(
        self, admin: User, target_user_id: uuid.UUID,
        ip: str | None = None, ua: str | None = None,
    ) -> dict:
        """Revoke all active sessions for target user."""
        await self._get_target_user(target_user_id)

        from app.modules.platform.auth.session.service import SessionService
        session_svc = SessionService(self.db)
        count = await session_svc.revoke_all_sessions(
            target_user_id, ip_address=ip, user_agent=ua,
        )

        from app.modules.platform.auth.audit import AuditService
        audit = AuditService(self.db)
        await audit.log(
            "operations.revoke_sessions",
            user_id=admin.id,
            ip_address=ip,
            user_agent=ua,
            target_user_id=str(target_user_id),
            sessions_revoked=count,
        )

        return {"revoked_count": count}

    async def disable_user_2fa(
        self, admin: User, target_user_id: uuid.UUID, admin_password: str,
        ip: str | None = None, ua: str | None = None,
    ) -> None:
        """Emergency disable 2FA for target user. Requires admin password."""
        self._verify_admin_password(admin, admin_password)
        target = await self._get_target_user(target_user_id)

        if not target.totp_enabled:
            raise ConflictError("2FA is niet ingeschakeld voor deze gebruiker.")

        # Rate limit: max 3 per hour per admin
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        count = (await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "operations.disable_2fa",
                AuditLog.user_id == admin.id,
                AuditLog.created_at > cutoff,
            )
        )).scalar() or 0
        if count >= 3:
            raise ForbiddenError("Maximaal 3 2FA-uitschakelingen per uur bereikt.")

        # Disable 2FA
        target.totp_enabled = False
        target.totp_secret_encrypted = None

        # Revoke all sessions
        from app.modules.platform.auth.session.service import SessionService
        session_svc = SessionService(self.db)
        await session_svc.revoke_all_sessions(
            target_user_id, ip_address=ip, user_agent=ua,
        )

        await self.db.flush()

        from app.modules.platform.auth.audit import AuditService
        audit = AuditService(self.db)
        await audit.log(
            "operations.disable_2fa",
            user_id=admin.id,
            ip_address=ip,
            user_agent=ua,
            target_user_id=str(target_user_id),
            target_email=target.email,
        )

    # ------------------------------------------------------------------
    # B3: Customer Timeline
    # ------------------------------------------------------------------

    # Category mapping: action prefix → category
    _ACTION_CATEGORIES: dict[str, str] = {
        "user.login": "login",
        "user.logout": "login",
        "session.": "login",
        "user.password_": "security",
        "user.2fa_": "security",
        "user.email_": "security",
        "operations.impersonate": "security",
        "operations.force_password_reset": "security",
        "operations.user_activated": "security",
        "operations.user_deactivated": "security",
        "operations.resend_verification": "security",
        "operations.revoke_sessions": "security",
        "operations.disable_2fa": "security",
        "student.": "data",
        "attendance.": "data",
        "schedule.": "data",
        "invitation.": "data",
        "billing.": "billing",
        "invoice.": "billing",
        "tenant.": "system",
        "superadmin.": "system",
    }

    # Human-readable summaries for common actions
    _ACTION_SUMMARIES: dict[str, str] = {
        "user.login": "Ingelogd",
        "user.login_2fa": "Ingelogd met 2FA",
        "user.logout": "Uitgelogd",
        "user.password_changed": "Wachtwoord gewijzigd",
        "user.password_reset_requested": "Wachtwoord reset aangevraagd",
        "user.password_reset_completed": "Wachtwoord gereset",
        "user.2fa_enabled": "2FA ingesteld",
        "user.2fa_disabled": "2FA uitgeschakeld",
        "user.email_verified": "E-mail geverifieerd",
        "student.created": "Nieuwe leerling aangemaakt",
        "student.updated": "Leerling bijgewerkt",
        "student.deleted": "Leerling verwijderd",
        "student.imported": "Leerlingen geïmporteerd",
        "attendance.created": "Aanwezigheid geregistreerd",
        "attendance.bulk_created": "Bulk aanwezigheid geregistreerd",
        "schedule.slot_created": "Lesslot aangemaakt",
        "schedule.slot_updated": "Lesslot bijgewerkt",
        "invitation.created": "Uitnodiging verstuurd",
        "invitation.accepted": "Uitnodiging geaccepteerd",
        "operations.force_password_reset": "Wachtwoord reset geforceerd",
        "operations.user_activated": "Account geactiveerd",
        "operations.user_deactivated": "Account gedeactiveerd",
        "operations.resend_verification": "Verificatie-email opnieuw verstuurd",
        "operations.revoke_sessions": "Sessies beëindigd",
        "operations.disable_2fa": "2FA uitgeschakeld (admin)",
    }

    @classmethod
    def _categorize_action(cls, action: str) -> str:
        """Map an audit action to a category."""
        # Try exact match first
        if action in cls._ACTION_CATEGORIES:
            return cls._ACTION_CATEGORIES[action]
        # Try prefix match
        for prefix, cat in cls._ACTION_CATEGORIES.items():
            if action.startswith(prefix):
                return cat
        return "system"

    @classmethod
    def _summarize_action(cls, action: str, details: dict | None) -> str | None:
        """Generate a human-readable summary for an action."""
        summary = cls._ACTION_SUMMARIES.get(action)
        if summary and details:
            # Enrich with details if available
            name = details.get("name") or details.get("student_name")
            if name and "leerling" in summary.lower():
                summary = f"{summary}: {name}"
            count = details.get("count")
            if count and "bulk" in action:
                summary = f"{count} {summary.lower()}"
        return summary

    @classmethod
    def _mask_ip(cls, ip: str | None) -> str | None:
        """Mask IP address for privacy (last octet/segment)."""
        if not ip:
            return None
        if ":" in ip:
            # IPv6: mask last 2 segments
            parts = ip.split(":")
            if len(parts) > 2:
                return ":".join(parts[:-2]) + ":x:x"
        elif "." in ip:
            # IPv4: mask last octet
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.x"
        return ip

    async def get_tenant_timeline(
        self,
        tenant_id: uuid.UUID,
        *,
        category: str | None = None,
        user_id: uuid.UUID | None = None,
        search: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TimelineResponse:
        """Enhanced tenant timeline with filters, categorization and IP masking."""
        # Verify tenant exists
        exists = (await self.db.execute(
            select(Tenant.id).where(Tenant.id == tenant_id)
        )).scalar_one_or_none()
        if not exists:
            raise NotFoundError("Tenant", str(tenant_id))

        # Build base query
        base_filter = [AuditLog.tenant_id == tenant_id]

        if user_id:
            base_filter.append(AuditLog.user_id == user_id)
        if date_from:
            base_filter.append(AuditLog.created_at >= date_from)
        if date_to:
            base_filter.append(AuditLog.created_at <= date_to)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            base_filter.append(AuditLog.action.ilike(f"%{escaped}%"))

        # Category filter: match action prefixes
        if category:
            cat_prefixes = [
                prefix for prefix, cat in self._ACTION_CATEGORIES.items()
                if cat == category
            ]
            if cat_prefixes:
                from sqlalchemy import or_
                base_filter.append(or_(
                    *[AuditLog.action.startswith(p.rstrip(".")) for p in cat_prefixes]
                ))

        # Count total
        count_q = select(func.count(AuditLog.id)).where(*base_filter)
        total_count = (await self.db.execute(count_q)).scalar() or 0

        # Fetch events
        result = await self.db.execute(
            select(
                AuditLog.id,
                AuditLog.action,
                AuditLog.ip_address,
                AuditLog.created_at,
                AuditLog.user_id,
                AuditLog.entity_type,
                AuditLog.entity_id,
                AuditLog.details,
                User.email.label("user_email"),
            )
            .outerjoin(User, AuditLog.user_id == User.id)
            .where(*base_filter)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        events = [
            TimelineEvent(
                id=row.id,
                action=row.action,
                category=self._categorize_action(row.action),
                user_email=row.user_email,
                user_id=row.user_id,
                ip_address=self._mask_ip(row.ip_address),
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                details_summary=self._summarize_action(row.action, row.details),
                created_at=row.created_at,
            )
            for row in result.all()
        ]

        return TimelineResponse(
            events=events,
            total_count=total_count,
            has_more=(offset + limit) < total_count,
        )

    # ------------------------------------------------------------------
    # B1: Impersonation
    # ------------------------------------------------------------------

    async def impersonate_user(
        self,
        admin: User,
        target_user_id: uuid.UUID,
        reason: str,
        tenant_id: uuid.UUID | None = None,
        ip: str | None = None,
        ua: str | None = None,
    ) -> ImpersonateResponse:
        """Start impersonation session for target user."""
        # Validation
        if target_user_id == admin.id:
            raise ForbiddenError("Je kunt jezelf niet impersonaten.")

        target = await self._get_target_user(target_user_id)
        if not target.is_active:
            raise ForbiddenError("Doelgebruiker is niet actief.")

        # Determine tenant context
        resolved_tenant_id = tenant_id
        if tenant_id:
            # Verify target has membership in that tenant
            membership = (await self.db.execute(
                select(TenantMembership).where(
                    TenantMembership.user_id == target_user_id,
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.is_active,
                )
            )).scalar_one_or_none()
            if not membership:
                raise ForbiddenError("Gebruiker is geen lid van deze organisatie.")
        else:
            # Use first active membership
            membership = (await self.db.execute(
                select(TenantMembership).where(
                    TenantMembership.user_id == target_user_id,
                    TenantMembership.is_active,
                )
            )).scalars().first()
            if membership:
                resolved_tenant_id = membership.tenant_id

        # Create impersonation token
        impersonation_id = uuid.uuid4()
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=app_settings.impersonation_token_expire_minutes,
        )

        access_token = create_impersonation_token(
            target_user_id=target.id,
            target_email=target.email,
            admin_user_id=admin.id,
            impersonation_id=impersonation_id,
            tenant_id=resolved_tenant_id,
        )

        # Audit log
        from app.modules.platform.auth.audit import AuditService
        audit = AuditService(self.db)
        await audit.log(
            "operations.impersonate_start",
            user_id=admin.id,
            ip_address=ip,
            user_agent=ua,
            target_user_id=str(target_user_id),
            target_email=target.email,
            reason=reason,
            impersonation_id=str(impersonation_id),
        )

        return ImpersonateResponse(
            access_token=access_token,
            target_user_email=target.email,
            target_user_name=target.full_name,
            expires_at=expires_at,
            impersonated_by=admin.id,
            impersonation_id=impersonation_id,
        )
