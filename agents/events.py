import asyncio
import logging
from typing import Any, Callable, Set

class AgentEventBus:
    """
    Central event dispatcher enabling loose coupling between the asynchronous
    agent loop / logging system and WebSocket clients.
    """
    def __init__(self):
        self._listeners: Set[Callable[[str, Any], Any]] = set()

    def register_listener(self, listener: Callable[[str, Any], Any]) -> None:
        """Registers an async or sync callback to receive all events."""
        self._listeners.add(listener)

    def unregister_listener(self, listener: Callable[[str, Any], Any]) -> None:
        """Removes a registered callback."""
        self._listeners.discard(listener)

    def emit(self, event_type: str, data: Any) -> None:
        """
        Broadcasts an event with a payload to all listeners in a non-blocking manner.
        """
        for listener in list(self._listeners):
            try:
                if asyncio.iscoroutinefunction(listener):
                    # Schedule async listener execution in the running loop
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(listener(event_type, data))
                    except RuntimeError:
                        # Fallback for threads or non-running loops
                        asyncio.run(listener(event_type, data))
                else:
                    listener(event_type, data)
            except Exception:
                pass  # Suppress individual listener issues to preserve execution stability

# Global Event Bus
event_bus = AgentEventBus()

class LogBroadcastHandler(logging.Handler):
    """
    Custom Python logging handler that routes log statements through the AgentEventBus
    to enable live streaming of execution logs on frontend dashboards.
    """
    def __init__(self, bus: AgentEventBus = event_bus):
        super().__init__()
        self.bus = bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.bus.emit("log", {
                "level": record.levelname,
                "name": record.name,
                "message": msg,
                "created": record.created
            })
        except Exception:
            self.handleError(record)
