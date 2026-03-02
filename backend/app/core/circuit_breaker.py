import asyncio
import time
from collections.abc import Callable, Coroutine
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker pattern implementation.

    - CLOSED: Normal operation, tracking failures.
    - OPEN: All calls fail fast after failure threshold exceeded.
    - HALF_OPEN: After recovery timeout, allow limited calls to test recovery.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable[..., Coroutine[Any, Any, T]], *args: Any, **kwargs: Any) -> T:
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.warning("circuit_breaker.open", name=self.name)
            raise CircuitOpenError(f"Circuit breaker '{self.name}' is open")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("circuit_breaker.closed", name=self.name)
            else:
                self._failure_count = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning(
                    "circuit_breaker.opened",
                    name=self.name,
                    failures=self._failure_count,
                )


class CircuitOpenError(Exception):
    pass


_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    success_threshold: int = 2,
) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
        )
    return _breakers[name]


def get_all_breaker_states() -> dict[str, dict[str, Any]]:
    """Return state info for all registered circuit breakers."""
    result = {}
    for name, breaker in _breakers.items():
        result[name] = {
            "state": breaker.state.value,
            "failure_count": breaker._failure_count,
            "failure_threshold": breaker.failure_threshold,
        }
    return result
