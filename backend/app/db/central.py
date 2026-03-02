from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# PgBouncer transaction pooling requires disabling asyncpg prepared statements
connect_args: dict = {}
pool_kwargs: dict = {"pool_size": 20, "max_overflow": 10}

if settings.use_pgbouncer:
    connect_args["prepared_statement_cache_size"] = 0
    pool_kwargs = {"pool_size": 5, "max_overflow": 3}

engine = create_async_engine(
    settings.central_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    connect_args=connect_args,
    **pool_kwargs,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_central_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
