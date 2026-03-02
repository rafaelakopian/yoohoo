import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

logger = structlog.get_logger()

EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """Async in-process event bus for decoupled module communication.

    Events are fire-and-forget: handler failures are logged but never
    propagate to the emitter. This ensures module isolation.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)
        logger.debug("event_bus.subscribed", event_name=event_name, handler=handler.__name__)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)

    async def emit(self, event_name: str, **kwargs: Any) -> None:
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            return

        logger.info("event_bus.emit", event_name=event_name, handler_count=len(handlers))

        tasks = []
        for handler in handlers:
            tasks.append(self._safe_call(event_name, handler, **kwargs))

        await asyncio.gather(*tasks)

    async def _safe_call(
        self, event_name: str, handler: EventHandler, **kwargs: Any
    ) -> None:
        try:
            await handler(**kwargs)
        except Exception:
            logger.exception(
                "event_bus.handler_error",
                event_name=event_name,
                handler=handler.__name__,
            )


event_bus = EventBus()
