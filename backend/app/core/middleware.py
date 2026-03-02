import time as _time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import structlog

from app.config import settings

logger = structlog.get_logger()


def get_client_ip(request: Request) -> str:
    """Extract the real client IP from X-Forwarded-For (behind proxy) or fall back to direct IP."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # First IP in the chain is the original client
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to each request for tracing."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all API responses.

    Acts as defense-in-depth alongside nginx headers.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "0")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cache-Control", "no-store")
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects requests with bodies exceeding the configured limit.

    Defense-in-depth alongside nginx's client_max_body_size.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_body_size:
            logger.warning(
                "request.body_too_large",
                content_length=content_length,
                limit=settings.max_request_body_size,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus metrics for HTTP requests."""

    SKIP_PATHS = {"/metrics", "/health/live", "/health/ready"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        method = request.method
        path_template = self._get_path_template(request)

        start = _time.perf_counter()
        response = await call_next(request)
        duration = _time.perf_counter() - start

        status = str(response.status_code)

        from app.core.metrics import (
            http_errors_total,
            http_request_duration_seconds,
            http_requests_total,
        )

        http_requests_total.labels(
            method=method, path_template=path_template, status_code=status
        ).inc()
        http_request_duration_seconds.labels(
            method=method, path_template=path_template
        ).observe(duration)

        if response.status_code >= 400:
            http_errors_total.labels(
                method=method, path_template=path_template, status_code=status
            ).inc()

        return response

    @staticmethod
    def _get_path_template(request: Request) -> str:
        """Extract the route template path to avoid high-cardinality labels."""
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            return route.path
        return request.url.path
