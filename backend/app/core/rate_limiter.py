import time
from collections import defaultdict
from collections.abc import Callable

import structlog
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings
from app.core.middleware import get_client_ip

logger = structlog.get_logger()

# In-memory fallback rate limiter (per-process, used when Redis is unavailable)
_memory_buckets: dict[str, list[float]] = defaultdict(list)
_MEMORY_MAX_KEYS = 10_000  # Prevent unbounded growth


def _memory_rate_check(key: str, max_requests: int, window_seconds: int) -> bool:
    """In-memory sliding window rate check. Returns True if allowed."""
    now = time.time()
    window_start = now - window_seconds
    bucket = _memory_buckets[key]
    # Purge expired entries
    _memory_buckets[key] = [t for t in bucket if t > window_start]
    if len(_memory_buckets[key]) >= max_requests:
        return False
    _memory_buckets[key].append(now)
    # Evict oldest keys if cache is too large
    if len(_memory_buckets) > _MEMORY_MAX_KEYS:
        oldest_key = min(_memory_buckets, key=lambda k: _memory_buckets[k][0] if _memory_buckets[k] else 0)
        del _memory_buckets[oldest_key]
    return True


def rate_limit(max_requests: int, window_seconds: int, key_prefix: str = "rl") -> Callable:
    """FastAPI Depends() for per-endpoint rate limiting via Redis.

    Usage: @router.post("/endpoint", dependencies=[Depends(rate_limit(3, 3600))])
    """

    async def _rate_limit_dep(request: Request) -> None:
        client_ip = get_client_ip(request)
        endpoint = request.url.path
        key = f"{key_prefix}:{endpoint}:{client_ip}"

        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            # Fallback to in-memory rate limiting
            if not _memory_rate_check(key, max_requests, window_seconds):
                raise HTTPException(
                    status_code=429,
                    detail="Te veel verzoeken. Probeer het later opnieuw.",
                    headers={"Retry-After": str(window_seconds)},
                )
            return

        try:
            now = time.time()
            window_start = now - window_seconds

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

            request_count = results[2]

            if request_count > max_requests:
                logger.warning(
                    "rate_limit.endpoint_exceeded",
                    client_ip=client_ip,
                    endpoint=endpoint,
                    count=request_count,
                )
                raise HTTPException(
                    status_code=429,
                    detail="Te veel verzoeken. Probeer het later opnieuw.",
                    headers={"Retry-After": str(window_seconds)},
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("rate_limit.redis_error", exc_info=True)

    return _rate_limit_dep


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis sliding window rate limiter.

    Falls back to no rate limiting if Redis is unavailable (degraded mode).
    """

    EXEMPT_PATHS = {"/health/live", "/health/ready", "/metrics"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = get_client_ip(request)
        key = f"rate_limit:{client_ip}"
        limit = settings.rate_limit_per_minute

        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            # Fallback to in-memory rate limiting (per-IP)
            if not _memory_rate_check(key, limit, 60):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )
            # Per-tenant in-memory fallback
            tenant_id = getattr(request.state, "tenant_id", None) if hasattr(request, "state") else None
            if tenant_id:
                tenant_key = f"rate_limit:tenant:{tenant_id}"
                if not _memory_rate_check(tenant_key, settings.rate_limit_per_tenant_per_minute, 60):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests for this organization"},
                        headers={"Retry-After": "60"},
                    )
            return await call_next(request)

        try:
            now = time.time()
            window_start = now - 60

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, 60)
            results = await pipe.execute()

            request_count = results[2]

            if request_count > limit:
                logger.warning("rate_limit.exceeded", client_ip=client_ip, count=request_count)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )

            # Per-tenant rate limiting (higher threshold, prevents one tenant from starving others)
            tenant_id = getattr(request.state, "tenant_id", None) if hasattr(request, "state") else None
            if tenant_id:
                tenant_key = f"rate_limit:tenant:{tenant_id}"
                tenant_limit = settings.rate_limit_per_tenant_per_minute

                pipe2 = redis.pipeline()
                pipe2.zremrangebyscore(tenant_key, 0, window_start)
                pipe2.zadd(tenant_key, {str(now): now})
                pipe2.zcard(tenant_key)
                pipe2.expire(tenant_key, 60)
                t_results = await pipe2.execute()

                tenant_count = t_results[2]
                if tenant_count > tenant_limit:
                    logger.warning(
                        "rate_limit.tenant_exceeded",
                        tenant_id=str(tenant_id),
                        count=tenant_count,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests for this organization"},
                        headers={"Retry-After": "60"},
                    )
        except Exception:
            logger.warning("rate_limit.redis_unavailable", exc_info=True)

        return await call_next(request)
