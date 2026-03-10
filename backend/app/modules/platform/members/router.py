from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import TenantMembership, User
from app.modules.platform.members.schemas import MemberListResponse
from app.modules.platform.members.service import MemberService

router = APIRouter(prefix="/access/users", tags=["members"])


@router.get("", response_model=MemberListResponse)
async def list_members(
    request: Request,
    group: str | None = Query(None, description="Filter by group slug (e.g. 'docent')"),
    q: str | None = Query(None, description="Search on name or email"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    """List members of the current organization."""
    tenant_id = request.state.tenant_id

    # Verify viewer is a member of this tenant (superadmin bypasses)
    if not current_user.is_superadmin:
        result = await db.execute(
            select(TenantMembership.id).where(
                TenantMembership.user_id == current_user.id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active,
            )
        )
        if not result.scalar_one_or_none():
            raise ForbiddenError("Not a member of this organization")

    service = MemberService(db)
    items, total = await service.list_members(
        tenant_id=tenant_id,
        viewer=current_user,
        group_slug=group,
        search=q,
        limit=limit,
        offset=offset,
    )
    return MemberListResponse(items=items, total=total)
