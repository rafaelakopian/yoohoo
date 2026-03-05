import enum
import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ForbiddenError, PermissionDeniedAsNotFound
from app.core.permissions import permission_registry
from app.core.security import _ua_fingerprint, decode_token
from app.db.central import get_central_db
from app.modules.platform.auth.constants import ROLE_HIERARCHY, Role
from app.modules.platform.auth.models import (
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.auth.core.service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(db: AsyncSession = Depends(get_central_db)) -> AuthService:
    return AuthService(db)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_central_db),
) -> User:
    if not credentials:
        raise AuthenticationError("Missing authentication token")

    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise AuthenticationError("Invalid or expired token")

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    # Impersonation claims
    impersonated_by = payload.get("impersonated_by")
    impersonation_id = payload.get("impersonation_id")
    request.state.impersonated_by = uuid.UUID(impersonated_by) if impersonated_by else None
    request.state.impersonation_id = uuid.UUID(impersonation_id) if impersonation_id else None

    # Token binding: verify user-agent fingerprint (skip during impersonation)
    if not impersonated_by:
        token_ua_fp = payload.get("ua_fp")
        if token_ua_fp:
            current_ua = request.headers.get("user-agent")
            current_fp = _ua_fingerprint(current_ua)
            if current_fp != token_ua_fp:
                raise AuthenticationError("Token gebonden aan ander apparaat")

    # Store session_id on request.state for downstream use (e.g. session router)
    session_id_str = payload.get("session_id")
    request.state.session_id = uuid.UUID(session_id_str) if session_id_str else None

    user_id = uuid.UUID(payload["sub"])
    service = AuthService(db)
    user = await service.get_user_with_memberships(user_id)

    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    return user


# --- Permission-based dependencies ---


def get_effective_permissions(user: User, tenant_id: uuid.UUID | None) -> set[str]:
    """Get the union of all permissions from the user's groups.

    Platform groups (tenant_id IS NULL) always apply.
    Tenant groups only apply when tenant_id matches.
    """
    if user.is_superadmin:
        return permission_registry.get_all_codenames()

    perms: set[str] = set()
    for assignment in user.group_assignments:
        # Platform groups (tenant_id is None) always apply
        if assignment.group.tenant_id is None:
            for gp in assignment.group.permissions:
                perms.add(gp.permission_codename)
        # Tenant groups only apply when tenant_id matches
        elif tenant_id and assignment.group.tenant_id == tenant_id:
            for gp in assignment.group.permissions:
                perms.add(gp.permission_codename)
    return perms


def require_permission(*required_permissions: str, hidden: bool = False):
    """Dependency factory that requires the user to have ALL listed permissions.

    Args:
        hidden: If True, returns 404 instead of 403 to hide resource existence.
    """

    async def _check_permission(
        current_user: User = Depends(get_current_user),
        request: Request = None,
        db: AsyncSession = Depends(get_central_db),
    ) -> User:
        if current_user.is_superadmin:
            return current_user

        tenant_id = getattr(request.state, "tenant_id", None) if request else None

        # Verify tenant membership when accessing tenant-scoped resources
        if tenant_id:
            result = await db.execute(
                select(TenantMembership.id).where(
                    TenantMembership.user_id == current_user.id,
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.is_active,
                )
            )
            if not result.scalar_one_or_none():
                raise PermissionDeniedAsNotFound() if hidden else ForbiddenError()

        effective = get_effective_permissions(current_user, tenant_id)

        for perm in required_permissions:
            if perm not in effective:
                raise PermissionDeniedAsNotFound() if hidden else ForbiddenError()

        return current_user

    return _check_permission


def require_any_permission(*required_permissions: str, hidden: bool = False):
    """Dependency factory that requires the user to have ANY ONE of the listed permissions.

    Args:
        hidden: If True, returns 404 instead of 403 to hide resource existence.
    """

    async def _check_permission(
        current_user: User = Depends(get_current_user),
        request: Request = None,
        db: AsyncSession = Depends(get_central_db),
    ) -> User:
        if current_user.is_superadmin:
            return current_user

        tenant_id = getattr(request.state, "tenant_id", None) if request else None

        # Verify tenant membership when accessing tenant-scoped resources
        if tenant_id:
            result = await db.execute(
                select(TenantMembership.id).where(
                    TenantMembership.user_id == current_user.id,
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.is_active,
                )
            )
            if not result.scalar_one_or_none():
                raise PermissionDeniedAsNotFound() if hidden else ForbiddenError()

        effective = get_effective_permissions(current_user, tenant_id)

        if not any(perm in effective for perm in required_permissions):
            raise PermissionDeniedAsNotFound() if hidden else ForbiddenError()

        return current_user

    return _check_permission


def is_data_restricted(user: User, tenant_id: uuid.UUID | None, full_perm: str) -> bool:
    """Check if user lacks the 'full' view permission (restricted to own data only).

    Returns True if the user does NOT have the full permission, meaning they should
    only see their own data (e.g. a parent seeing only their linked children).
    """
    if user.is_superadmin:
        return False
    effective = get_effective_permissions(user, tenant_id)
    return full_perm not in effective


class DataScope(str, enum.Enum):
    """Three-way data visibility scope for multi-docent support."""
    all = "all"           # module.view → sees everything
    assigned = "assigned"  # module.view_assigned → sees own assigned students (teacher)
    own = "own"           # module.view_own → sees own linked children (parent)


def get_data_scope(user: User, tenant_id: uuid.UUID | None, module: str) -> DataScope:
    """Determine the data visibility scope for a user in a module.

    Priority: all > assigned > own.
    The module parameter is the permission prefix (e.g. "students", "attendance", "schedule").
    """
    if user.is_superadmin:
        return DataScope.all

    effective = get_effective_permissions(user, tenant_id)

    if f"{module}.view" in effective:
        return DataScope.all
    if f"{module}.view_assigned" in effective:
        return DataScope.assigned
    if f"{module}.view_own" in effective:
        return DataScope.own

    # Fallback — should not happen if require_any_permission() guard already passed
    return DataScope.own


# --- Platform user check ---


async def is_platform_user(user_id: uuid.UUID, db: AsyncSession) -> bool:
    """Check if a user is a platform-level user (superadmin or has platform group assignments).

    Platform users must NEVER have TenantMembership records.
    """
    from app.modules.platform.auth.models import User as UserModel

    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    if user.is_superadmin:
        return True
    # Check for platform group assignments (groups with tenant_id IS NULL)
    result = await db.execute(
        select(UserGroupAssignment)
        .join(PermissionGroup)
        .where(
            UserGroupAssignment.user_id == user_id,
            PermissionGroup.tenant_id == None,  # noqa: E711
        )
    )
    return result.scalar_one_or_none() is not None


# --- Deprecated role-based dependencies (kept for backward compatibility) ---


def require_role(minimum_role: Role):
    """DEPRECATED: Use require_permission() instead.

    Kept for backward compatibility during transition.
    """

    async def _check_role(
        current_user: User = Depends(get_current_user),
        request: Request = None,
    ) -> User:
        if current_user.is_superadmin:
            return current_user

        tenant_id = getattr(request.state, "tenant_id", None) if request else None
        min_level = ROLE_HIERARCHY[minimum_role]

        for membership in current_user.memberships:
            if tenant_id and membership.tenant_id != tenant_id:
                continue
            if not membership.is_active:
                continue
            if membership.role and ROLE_HIERARCHY.get(membership.role, -1) >= min_level:
                return current_user

        raise ForbiddenError()

    return _check_role


