import re
import subprocess

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

logger = structlog.get_logger()

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def _validate_slug(slug: str) -> None:
    """Validate slug contains only safe characters for use in database names."""
    if not _SLUG_PATTERN.match(slug):
        raise ValueError(f"Invalid tenant slug: {slug!r}")


async def create_tenant_database(slug: str) -> None:
    """Create a new PostgreSQL database for a tenant and run Alembic migrations."""
    _validate_slug(slug)

    db_name = settings.tenant_db_name(slug)
    logger.info("tenant_db.creating", database=db_name)

    # Connect to the admin database to create the new one
    engine = create_async_engine(settings.postgres_admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        # Check if database already exists
        result = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        )
        if result.scalar():
            logger.info("tenant_db.already_exists", database=db_name)
            await engine.dispose()
            return

        await conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    await engine.dispose()

    # Run Alembic migrations on the new tenant database
    result = subprocess.run(
        [
            "alembic",
            "-x", "mode=tenant",
            "-x", f"tenant_slug={slug}",
            "upgrade", "tenant@head",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(
            "tenant_db.migration_failed",
            database=db_name,
            stderr=result.stderr,
        )
        # Do not include stderr in the exception — it may contain connection strings
        raise RuntimeError(f"Database migration failed for tenant '{slug}'.")

    logger.info("tenant_db.created", database=db_name)


async def drop_tenant_database(slug: str) -> None:
    """Drop a tenant database. Use with extreme caution."""
    _validate_slug(slug)

    db_name = settings.tenant_db_name(slug)
    logger.warning("tenant_db.dropping", database=db_name)

    engine = create_async_engine(settings.postgres_admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        # Terminate existing connections
        await conn.execute(
            text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": db_name},
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))

    await engine.dispose()
    logger.info("tenant_db.dropped", database=db_name)
