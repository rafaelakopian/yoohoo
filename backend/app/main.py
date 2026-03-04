from contextlib import asynccontextmanager

import redis.asyncio as redis
import sentry_sdk
import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import AppException, app_exception_handler, unhandled_exception_handler
from app.core.health import branding_router, health_registry, metrics_router, router as health_router
from app.core.logging_config import setup_logging
from app.core.middleware import MaxBodySizeMiddleware, PrometheusMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.rate_limiter import RateLimitMiddleware
from app.db.central import engine as central_engine
from app.db.tenant import tenant_db_manager
from app.modules.platform.auth.core.router import router as auth_router
from app.modules.platform.auth.password.router import router as password_router
from app.modules.platform.auth.session.router import router as session_router
from app.modules.platform.auth.invitation.router import org_router as invitation_org_router
from app.modules.platform.auth.invitation.router import auth_router as invitation_auth_router
from app.modules.platform.auth.totp.router import router as totp_router
from app.modules.platform.auth.permissions.router import (
    platform_router as permissions_platform_router,
    tenant_router as permissions_tenant_router,
)
from app.modules.tenant.attendance.router import router as attendance_router
from app.modules.tenant.notification.router import router as notification_router
from app.modules.tenant.notification.setup import register_notification_handlers
from app.modules.tenant.schedule.router import router as schedule_router
from app.modules.tenant.student.router import router as student_router
from app.modules.platform.admin.router import router as admin_router
from app.modules.platform.tenant_mgmt.router import router as tenant_router
from app.modules.platform.billing.router import router as billing_router
from app.modules.platform.billing.webhooks.router import router as webhook_router
from app.modules.tenant.billing.router import router as tuition_router
from app.modules.platform.auth.collaboration.router import router as collaboration_router
from app.modules.platform.members.router import router as members_router
from app.modules.tenant.path_dependency import resolve_tenant_from_path

import app.modules.platform.auth.collaboration  # noqa: F401 (register permissions)

logger = structlog.get_logger()


async def check_postgres() -> bool:
    try:
        async with central_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis(app_state) -> bool:
    try:
        r = getattr(app_state, "redis", None)
        if r is None:
            return False
        await r.ping()
        return True
    except Exception:
        return False


async def check_pgbouncer() -> bool:
    """Check PgBouncer is reachable (same as postgres check — query goes through PgBouncer)."""
    if not settings.use_pgbouncer:
        return True  # Not enabled, always healthy
    return await check_postgres()


async def check_arq_worker(app_state) -> bool:
    """Check arq worker is reachable via Redis."""
    try:
        arq_pool = getattr(app_state, "arq", None)
        if arq_pool is None:
            return False
        # Check Redis connection used by arq
        await arq_pool.info()
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("app.starting", env=settings.app_env)

    # Initialize Sentry error tracking
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.sentry_environment or settings.app_env,
            release="yoohoo-api@1.0.0",
            send_default_pii=False,
        )
        logger.info("sentry.initialized")

    # Validate secrets are not defaults in production
    if settings.app_env != "development":
        if "change-me" in settings.secret_key:
            raise RuntimeError("FATAL: secret_key is still the default value. Set a proper secret in .env")
        if "change-me" in settings.jwt_secret_key:
            raise RuntimeError("FATAL: jwt_secret_key is still the default value. Set a proper secret in .env")
        if settings.postgres_password == "yoohoo_secret":
            raise RuntimeError("FATAL: postgres_password is still the default value. Set a proper password in .env")

        # Warn if CORS origins use HTTP in production
        for origin in settings.cors_origins_list:
            if origin.startswith("http://"):
                logger.warning(
                    "security.cors_http_origin",
                    origin=origin,
                    msg="CORS origin uses HTTP — use HTTPS in production",
                )

    # Connect Redis (graceful - app works without it)
    try:
        app.state.redis = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await app.state.redis.ping()
        logger.info("redis.connected")
    except Exception:
        logger.warning("redis.unavailable", msg="Running without Redis")
        app.state.redis = None

    # Connect arq pool for job enqueueing
    try:
        app.state.arq = await create_pool(RedisSettings(
            host=settings.redis_host,
            port=settings.redis_port,
            database=settings.arq_redis_db,
        ))
        logger.info("arq.pool_connected", redis_db=settings.arq_redis_db)
    except Exception:
        logger.warning("arq.pool_unavailable", msg="Running without arq job queue")
        app.state.arq = None

    # Register health checks
    health_registry.register("postgres", check_postgres)
    health_registry.register("redis", lambda: check_redis(app.state))
    if settings.use_pgbouncer:
        health_registry.register("pgbouncer", check_pgbouncer)
    health_registry.register("arq_worker", lambda: check_arq_worker(app.state))

    # Initialize email providers (fail-fast on misconfig, not on connectivity)
    from app.core.email import _get_providers
    try:
        _get_providers()
    except ValueError as e:
        raise RuntimeError(f"FATAL: email provider misconfiguration: {e}") from e

    # Register notification event handlers (with arq pool for background jobs)
    register_notification_handlers(arq_pool=app.state.arq)

    # Set Prometheus app info
    from app.core.metrics import app_info
    app_info.info({"version": "1.0.0", "env": settings.app_env})

    yield

    # Shutdown
    logger.info("app.shutting_down")
    from app.core.email import close_providers
    await close_providers()
    if app.state.arq:
        await app.state.arq.close()
    if app.state.redis:
        await app.state.redis.close()
    await tenant_db_manager.close_all()
    await central_engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Middleware (order matters: last added = first executed)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MaxBodySizeMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(PrometheusMiddleware)  # Outermost — captures full request lifecycle

    # --- Platform routers (no tenant context) ---
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(branding_router)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(password_router, prefix=settings.api_v1_prefix)
    app.include_router(session_router, prefix=settings.api_v1_prefix)
    app.include_router(invitation_auth_router, prefix=settings.api_v1_prefix)
    app.include_router(invitation_org_router, prefix=settings.api_v1_prefix)
    app.include_router(totp_router, prefix=settings.api_v1_prefix)
    app.include_router(permissions_platform_router, prefix=settings.api_v1_prefix)
    app.include_router(tenant_router, prefix=settings.api_v1_prefix)
    app.include_router(admin_router, prefix=settings.api_v1_prefix)
    app.include_router(billing_router, prefix=settings.api_v1_prefix)
    app.include_router(webhook_router, prefix=settings.api_v1_prefix)

    # --- Tenant-scoped routers (slug-in-URL, /orgs/{slug}/...) ---
    tenant_parent = APIRouter(
        prefix="/orgs/{slug}",
        dependencies=[Depends(resolve_tenant_from_path)],
    )
    tenant_parent.include_router(student_router)
    tenant_parent.include_router(attendance_router)
    tenant_parent.include_router(schedule_router)
    tenant_parent.include_router(notification_router)
    tenant_parent.include_router(tuition_router)
    tenant_parent.include_router(collaboration_router)
    tenant_parent.include_router(members_router)
    tenant_parent.include_router(permissions_tenant_router)

    app.include_router(tenant_parent, prefix=settings.api_v1_prefix)

    return app


app = create_app()
