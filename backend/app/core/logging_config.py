import logging
import re
import sys
from typing import Any

import structlog

from app.config import settings


def _mask_email(email: str) -> str:
    """Mask an email address: user@domain.com → u***@domain.com"""
    at = email.find("@")
    if at <= 0:
        return "***"
    return email[0] + "***" + email[at:]


_DB_URL_PATTERN = re.compile(
    r"postgresql(?:\+asyncpg)?://[^@]+@"
)


def _redact_pii_processor(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor that masks emails and database URLs in log output."""
    # Mask known email fields
    for key in ("email", "new_email", "old_email"):
        if key in event_dict and isinstance(event_dict[key], str):
            event_dict[key] = _mask_email(event_dict[key])

    # Redact database URLs (postgresql://user:pass@host)
    for key, value in event_dict.items():
        if isinstance(value, str) and _DB_URL_PATTERN.search(value):
            event_dict[key] = _DB_URL_PATTERN.sub("postgresql://***:***@", value)

    return event_dict


def setup_logging() -> None:
    """Configure structured logging with structlog."""

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _redact_pii_processor,
    ]

    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )
