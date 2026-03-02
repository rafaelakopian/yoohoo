"""Audit dependency for tenant-scoped routes."""

import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.middleware import get_client_ip
from app.db.central import async_session_factory
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User

logger = structlog.get_logger()


class TenantAuditHelper:
    """Provides audit logging for tenant-scoped operations.

    Uses its own central DB session, independent of the tenant DB session.
    """

    def __init__(self, db: AsyncSession, user: User, request: Request):
        self._audit = AuditService(db)
        self._db = db
        self._user = user
        self._tenant_id: uuid.UUID | None = getattr(request.state, "tenant_id", None)
        self._ip = get_client_ip(request)
        self._ua = request.headers.get("User-Agent")

    async def log(
        self,
        action: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        **details: object,
    ) -> None:
        """Log a tenant-scoped audit event. Best-effort: never fails the main request."""
        try:
            await self._audit.log(
                action=action,
                user_id=self._user.id,
                ip_address=self._ip,
                user_agent=self._ua,
                tenant_id=self._tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                **details,
            )
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            logger.warning(
                "audit.write_failed",
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
            )


async def get_tenant_audit(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AsyncGenerator[TenantAuditHelper, None]:
    """Dependency: provides TenantAuditHelper with its own central DB session."""
    async with async_session_factory() as session:
        yield TenantAuditHelper(session, current_user, request)
