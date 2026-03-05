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

from app.core.exceptions import NotFoundError
from app.db.tenant import TenantDatabaseManager, tenant_db_manager
from app.modules.platform.auth.models import (
    AuditLog,
    PermissionGroup,
    RefreshToken,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.operations.metrics import TenantMetricsCollector
from app.modules.platform.operations.schemas import (
    AuditEvent,
    InvoiceStats,
    OnboardingItem,
    Tenant360Detail,
    Tenant360Member,
    TenantHealthDashboard,
    TenantHealthItem,
    TenantSettingsSummary,
    UserLookupMembership,
    UserLookupResult,
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
                role=m.role.value if m.role else None,
                is_active=m.is_active,
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
    # A3: User Lookup
    # ------------------------------------------------------------------

    async def lookup_user(self, query: str, limit: int = 20) -> list[UserLookupResult]:
        """Search users by email or name (ILIKE). Minimum 3 characters enforced."""
        if len(query) < 3:
            return []

        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_filter = f"%{escaped}%"

        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.memberships).selectinload(TenantMembership.tenant),
                selectinload(User.group_assignments).selectinload(UserGroupAssignment.group),
            )
            .where(
                (User.email.ilike(search_filter)) | (User.full_name.ilike(search_filter))
            )
            .order_by(User.full_name)
            .limit(limit)
        )
        users = result.scalars().all()

        items = []
        for user in users:
            # Group names per tenant
            tenant_groups: dict[uuid.UUID, list[str]] = {}
            for a in user.group_assignments:
                tid = a.group.tenant_id
                if tid:
                    tenant_groups.setdefault(tid, []).append(a.group.name)

            # Memberships
            memberships = [
                UserLookupMembership(
                    tenant_id=m.tenant_id,
                    tenant_name=m.tenant.name if m.tenant else "?",
                    tenant_slug=m.tenant.slug if m.tenant else "?",
                    role=m.role.value if m.role else None,
                    groups=tenant_groups.get(m.tenant_id, []),
                )
                for m in user.memberships
                if m.is_active
            ]

            # Active sessions count
            session_count = (await self.db.execute(
                select(func.count(RefreshToken.id)).where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked.is_(False),
                    RefreshToken.expires_at > datetime.now(timezone.utc),
                )
            )).scalar() or 0

            items.append(UserLookupResult(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_superadmin=user.is_superadmin,
                email_verified=user.email_verified,
                totp_enabled=user.totp_enabled,
                last_login_at=user.last_login_at,
                created_at=user.created_at,
                memberships=memberships,
                active_sessions=session_count,
            ))

        return items

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
