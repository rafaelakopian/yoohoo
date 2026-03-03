"""Session management service."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.models import RefreshToken
from app.modules.platform.auth.session.schemas import SessionInfo

logger = structlog.get_logger()


class SessionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def list_sessions(
        self, user_id: uuid.UUID, current_session_id: uuid.UUID | None = None
    ) -> list[SessionInfo]:
        """List all active (non-revoked, non-expired) sessions for a user."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                not RefreshToken.revoked,
                RefreshToken.expires_at > now,
            ).order_by(RefreshToken.created_at.desc())
        )
        tokens = result.scalars().all()
        sessions = []
        for t in tokens:
            sessions.append(
                SessionInfo(
                    id=t.id,
                    created_at=t.created_at,
                    expires_at=t.expires_at,
                    ip_address=t.ip_address,
                    user_agent=t.user_agent,
                    is_current=(t.id == current_session_id) if current_session_id else False,
                )
            )
        return sessions

    async def revoke_session(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Revoke a specific session (refresh token). Must belong to the user."""
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.id == session_id,
                RefreshToken.user_id == user_id,
                not RefreshToken.revoked,
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            raise NotFoundError("Session", str(session_id))

        token.revoked = True
        await self.db.flush()

        await self.audit.log(
            "session.revoked",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=str(session_id),
        )
        logger.info("session.revoked", user_id=str(user_id), session_id=str(session_id))

    async def revoke_all_sessions(
        self,
        user_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> int:
        """Revoke all active sessions for a user. Returns count."""
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, not RefreshToken.revoked)
            .values(revoked=True)
        )
        count = result.rowcount
        await self.db.flush()

        await self.audit.log(
            "user.logout_all",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            sessions_revoked=count,
        )
        logger.info("session.revoke_all", user_id=str(user_id), count=count)
        return count
