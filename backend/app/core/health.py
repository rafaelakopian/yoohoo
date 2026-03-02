import ipaddress
from collections.abc import Callable, Coroutine
from typing import Any

import structlog
from fastapi import APIRouter, Request

from app.config import settings
from app.core.middleware import get_client_ip
from app.core.circuit_breaker import get_all_breaker_states

logger = structlog.get_logger()

HealthCheck = Callable[[], Coroutine[Any, Any, bool]]


class HealthRegistry:
    """Registry for health check functions."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}

    def register(self, name: str, check: HealthCheck) -> None:
        self._checks[name] = check

    async def run_all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        all_healthy = True

        for name, check in self._checks.items():
            try:
                healthy = await check()
                results[name] = {"status": "healthy" if healthy else "unhealthy"}
                if not healthy:
                    all_healthy = False
            except Exception as e:
                results[name] = {"status": "unhealthy"}
                all_healthy = False
                logger.warning("health_check_failed", check=name, error=str(e))

        return {"healthy": all_healthy, "checks": results}


health_registry = HealthRegistry()

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Simple liveness probe - always returns OK if the process is running."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness():
    """Readiness probe - checks all registered health checks."""
    result = await health_registry.run_all()
    status_code = 200 if result["healthy"] else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(content=result, status_code=status_code)


@router.get("/circuit-breakers")
async def circuit_breakers():
    """Return states of all circuit breakers."""
    return get_all_breaker_states()


# --- Metrics ---

metrics_router = APIRouter(tags=["metrics"])


_PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
)


def _is_internal(ip_str: str) -> bool:
    """Check if an IP address belongs to a private/internal network."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


@metrics_router.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request):
    """Prometheus metrics endpoint for scraping. Restricted to internal IPs."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    from starlette.responses import Response as StarletteResponse

    client_ip = get_client_ip(request)
    if not _is_internal(client_ip) and settings.app_env != "development":
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    return StarletteResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# --- Branding ---

branding_router = APIRouter(tags=["branding"])


@branding_router.get("/branding")
async def get_branding():
    """Public endpoint returning platform branding configuration."""
    return {
        "platform_name": settings.platform_name,
        "platform_name_short": settings.platform_name_short,
        "platform_url": settings.platform_url,
    }
