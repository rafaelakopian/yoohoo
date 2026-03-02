import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# PgBouncer transaction pooling requires disabling asyncpg prepared statements
_connect_args: dict = {}
_pool_kwargs: dict = {"pool_size": 10, "max_overflow": 5}

if settings.use_pgbouncer:
    _connect_args["prepared_statement_cache_size"] = 0
    _pool_kwargs = {"pool_size": 3, "max_overflow": 2}


class TenantDatabaseManager:
    """Manages per-tenant database connections with lazy engine caching."""

    def __init__(self) -> None:
        self._engines: dict[str, AsyncEngine] = {}
        self._session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}
        self._lock = asyncio.Lock()

    async def get_engine(self, tenant_slug: str) -> AsyncEngine:
        if tenant_slug not in self._engines:
            async with self._lock:
                if tenant_slug not in self._engines:
                    url = settings.tenant_database_url(tenant_slug)
                    engine = create_async_engine(
                        url,
                        echo=settings.debug,
                        pool_pre_ping=True,
                        connect_args=_connect_args,
                        **_pool_kwargs,
                    )
                    self._engines[tenant_slug] = engine
                    self._session_factories[tenant_slug] = async_sessionmaker(
                        engine,
                        class_=AsyncSession,
                        expire_on_commit=False,
                    )
        return self._engines[tenant_slug]

    async def get_session(self, tenant_slug: str) -> AsyncGenerator[AsyncSession, None]:
        await self.get_engine(tenant_slug)
        factory = self._session_factories[tenant_slug]
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close_all(self) -> None:
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()
        self._session_factories.clear()

    async def remove_engine(self, tenant_slug: str) -> None:
        if tenant_slug in self._engines:
            await self._engines[tenant_slug].dispose()
            del self._engines[tenant_slug]
            del self._session_factories[tenant_slug]


tenant_db_manager = TenantDatabaseManager()
