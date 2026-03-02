import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.modules.platform.auth.core.schemas import MessageResponse
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.auth.session.schemas import SessionInfo
from app.modules.platform.auth.session.service import SessionService

router = APIRouter(prefix="/auth", tags=["auth-sessions"])


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = SessionService(db)
    current_session_id = getattr(request.state, "session_id", None)
    return await service.list_sessions(current_user.id, current_session_id=current_session_id)


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = SessionService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await service.revoke_session(current_user.id, session_id, ip_address=ip, user_agent=ua)
    return MessageResponse(message="Sessie beëindigd")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    service = SessionService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    count = await service.revoke_all_sessions(current_user.id, ip_address=ip, user_agent=ua)
    return MessageResponse(message=f"{count} sessie(s) beëindigd")
