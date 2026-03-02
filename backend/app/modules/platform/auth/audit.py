"""Audit logging service for security events."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import AuditLog

logger = structlog.get_logger()


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        tenant_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        **details: object,
    ) -> None:
        """Log an audit event. Supports both platform and tenant-scoped actions."""
        entry = AuditLog(
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details if details else None,
        )
        self.db.add(entry)
        await self.db.flush()
        logger.info(
            "audit.logged",
            action=action,
            user_id=str(user_id) if user_id else None,
            tenant_id=str(tenant_id) if tenant_id else None,
        )
