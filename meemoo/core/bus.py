"""Async pub/sub event bus — the nervous system (Constitution Art. II §2).

Modules communicate ONLY through this bus. No module imports another module's
internals; that is what makes the hardware swap possible.

Features:
- typed topic strings (see :mod:`meemoo.core.topics`)
- wildcard subscribe (``person.*``, ``*``)
- replay-last-event per topic for late subscribers
- async-iterator subscriptions with explicit unsubscribe
- safe under concurrent publishers (monotonic sequence numbers)
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from meemoo.core.topics import topic_matches

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Event:
    """A single bus event. ``payload`` must be JSON-serializable."""

    topic: str
    payload: dict[str, object] = field(default_factory=dict)
    seq: int = 0
    ts: float = 0.0


class Subscription:
    """A live subscription: iterate with ``async for``, or ``await sub.get()``.

    Created via :meth:`EventBus.subscribe`; call :meth:`close` (or use the bus's
    ``unsubscribe``) when done. Iteration ends after ``close()`` once the queue
    drains.
    """

    _CLOSED = object()

    def __init__(self, bus: EventBus, patterns: tuple[str, ...]) -> None:
        self._bus = bus
        self.patterns = patterns
        self._queue: asyncio.Queue[Event | object] = asyncio.Queue()
        self._closed = False

    def matches(self, topic: str) -> bool:
        return any(topic_matches(p, topic) for p in self.patterns)

    def _deliver(self, event: Event) -> None:
        if not self._closed:
            self._queue.put_nowait(event)

    async def get(self) -> Event:
        """Wait for the next matching event. Raises after close + drain."""
        item = await self._queue.get()
        if item is Subscription._CLOSED:
            raise EventBusClosedError("subscription closed")
        assert isinstance(item, Event)
        return item

    def close(self) -> None:
        """Unsubscribe. Queued events remain readable; iteration then stops."""
        if self._closed:
            return
        self._closed = True
        self._bus._detach(self)
        self._queue.put_nowait(Subscription._CLOSED)

    def __aiter__(self) -> AsyncIterator[Event]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[Event]:
        while True:
            item = await self._queue.get()
            if item is Subscription._CLOSED:
                return
            assert isinstance(item, Event)
            yield item


class EventBusClosedError(RuntimeError):
    """Raised when reading from a closed subscription."""


class EventBus:
    """Process-wide async pub/sub with replay-last for late subscribers."""

    def __init__(self) -> None:
        self._subs: list[Subscription] = []
        self._last_by_topic: dict[str, Event] = {}
        self._seq = itertools.count(1)
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, payload: dict[str, object] | None = None) -> Event:
        """Publish an event; delivery to all matching subscribers is immediate.

        Safe to call from many tasks concurrently: the lock makes sequence
        assignment + fan-out atomic, so every subscriber sees a consistent,
        monotonically increasing ``seq``.
        """
        async with self._lock:
            event = Event(
                topic=topic,
                payload=dict(payload or {}),
                seq=next(self._seq),
                ts=time.time(),
            )
            self._last_by_topic[topic] = event
            for sub in list(self._subs):
                if sub.matches(topic):
                    sub._deliver(event)
        logger.debug("bus publish", extra={"fields": {"topic": topic, "seq": event.seq}})
        return event

    def subscribe(self, *patterns: str, replay_last: bool = True) -> Subscription:
        """Subscribe to one or more topic patterns (exact, ``x.*``, or ``*``).

        With ``replay_last`` (default), the most recent past event of every
        matching topic is queued immediately — late subscribers still learn
        current state (e.g. last ``flight.battery``).
        """
        if not patterns:
            raise ValueError("subscribe() needs at least one topic pattern")
        sub = Subscription(self, patterns)
        if replay_last:
            for event in sorted(self._last_by_topic.values(), key=lambda e: e.seq):
                if sub.matches(event.topic):
                    sub._deliver(event)
        self._subs.append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        """Close ``sub``; equivalent to ``sub.close()``."""
        sub.close()

    def _detach(self, sub: Subscription) -> None:
        if sub in self._subs:
            self._subs.remove(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def last(self, topic: str) -> Event | None:
        """The most recent event published on exactly ``topic``, if any."""
        return self._last_by_topic.get(topic)
