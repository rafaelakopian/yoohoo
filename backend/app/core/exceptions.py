from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str, identifier: str | None = None):
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} '{identifier}' not found"
        super().__init__(msg, status_code=404)


class ConflictError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class ForbiddenError(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message, status_code=403)


class PermissionDeniedAsNotFound(AppException):
    """Return 404 instead of 403 — hides resource existence from unauthorized users."""
    def __init__(self):
        super().__init__("Not found", status_code=404)


class TenantNotFoundError(NotFoundError):
    def __init__(self, identifier: str | None = None):
        super().__init__("Tenant", identifier)


class TenantDatabaseError(AppException):
    def __init__(self, tenant_slug: str, detail: str | None = None):
        # Log the slug server-side but don't expose it to the client
        logger.error("tenant_database_error", tenant_slug=tenant_slug, detail=detail)
        super().__init__(
            "Database service temporarily unavailable",
            status_code=503,
        )


class AuthenticationError(AppException):
    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(message, status_code=401)


class ValidationError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        "app_exception",
        status_code=exc.status_code,
        message=exc.message,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
