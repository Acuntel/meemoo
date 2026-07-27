"""Process-wide handle to the running EventBus (guardian/flight registry twin).

The API layer's live endpoints (/ws/events, round trigger, /ws/voice) need
the bus the runtime wired — but api/ must not construct module internals
(Art. II §2). Whoever wires the app registers the bus here. With none
registered the endpoints answer honestly (``ready: False``) and nothing
crashes (Art. IX §3).
"""

from __future__ import annotations

from meemoo.core.bus import EventBus

_active: EventBus | None = None


def set_active_bus(bus: EventBus | None) -> None:
    """Register (or clear) the running bus for API access."""
    global _active
    _active = bus


def get_active_bus() -> EventBus | None:
    return _active


# Same idiom for the check-in scheduler: schedule EDITS through the REST API
# must retune the running cron jobs without a server restart. Typed loosely
# (object) to avoid a core->guardian import; the API casts via a Protocol.
_active_scheduler: object | None = None


def set_active_scheduler(scheduler: object | None) -> None:
    """Register (or clear) the running check-in scheduler for API access."""
    global _active_scheduler
    _active_scheduler = scheduler


def get_active_scheduler() -> object | None:
    return _active_scheduler
