"""Thread-safe signal suppression for event-related side effects.

Uses `contextvars.ContextVar` instead of `post_save.disconnect()` to ensure
suppression is scoped to the current execution context (thread/coroutine),
not applied globally.
"""

import typing as t
from contextlib import contextmanager
from contextvars import ContextVar

__all__ = [
    "is_event_notifications_suppressed",
    "suppress_event_notifications",
]

_suppress_event_notifications: ContextVar[bool] = ContextVar("_suppress_event_notifications", default=False)


def is_event_notifications_suppressed() -> bool:
    """Return whether event notifications are suppressed in this context."""
    return _suppress_event_notifications.get()


@contextmanager
def suppress_event_notifications() -> t.Iterator[None]:
    """Suppress EVENT_OPEN and follower notifications for events saved in this context.

    Used during batch materialization of recurring events to avoid notification spam.
    A single digest notification should be sent after the batch completes.
    """
    token = _suppress_event_notifications.set(True)
    try:
        yield
    finally:
        _suppress_event_notifications.reset(token)
