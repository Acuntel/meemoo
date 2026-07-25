"""Event bus tests: pub/sub, wildcard, replay, unsubscribe, concurrency."""

from __future__ import annotations

import asyncio

import pytest

from meemoo.core import topics
from meemoo.core.bus import EventBus, EventBusClosedError


async def test_pub_sub_basic() -> None:
    bus = EventBus()
    sub = bus.subscribe(topics.PERSON_DOWN)
    await bus.publish(topics.PERSON_DOWN, {"person_id": 1})
    event = await asyncio.wait_for(sub.get(), timeout=1)
    assert event.topic == topics.PERSON_DOWN
    assert event.payload == {"person_id": 1}
    assert event.seq == 1
    assert event.ts > 0


async def test_subscriber_only_gets_matching_topics() -> None:
    bus = EventBus()
    sub = bus.subscribe(topics.PERSON_DOWN)
    await bus.publish(topics.UTTERANCE_HEARD, {"text": "hi"})
    await bus.publish(topics.PERSON_DOWN)
    event = await asyncio.wait_for(sub.get(), timeout=1)
    assert event.topic == topics.PERSON_DOWN


async def test_wildcard_subscribe() -> None:
    bus = EventBus()
    person_sub = bus.subscribe("person.*")
    all_sub = bus.subscribe("*")
    await bus.publish(topics.PERSON_DETECTED)
    await bus.publish(topics.FLIGHT_BATTERY, {"pct": 80})
    await bus.publish(topics.PERSON_RECOVERED)

    got = [await person_sub.get(), await person_sub.get()]
    assert [e.topic for e in got] == [topics.PERSON_DETECTED, topics.PERSON_RECOVERED]
    everything = [await all_sub.get() for _ in range(3)]
    assert [e.topic for e in everything] == [
        topics.PERSON_DETECTED,
        topics.FLIGHT_BATTERY,
        topics.PERSON_RECOVERED,
    ]


async def test_replay_last_for_late_subscriber() -> None:
    bus = EventBus()
    await bus.publish(topics.FLIGHT_BATTERY, {"pct": 90})
    await bus.publish(topics.FLIGHT_BATTERY, {"pct": 85})  # only the LAST replays
    await bus.publish(topics.DOCK_CHARGING, {"on": True})

    late = bus.subscribe("flight.*", topics.DOCK_CHARGING)
    first = await asyncio.wait_for(late.get(), timeout=1)
    second = await asyncio.wait_for(late.get(), timeout=1)
    assert first.topic == topics.FLIGHT_BATTERY
    assert first.payload == {"pct": 85}
    assert second.topic == topics.DOCK_CHARGING
    assert first.seq < second.seq  # replay preserves original publish order


async def test_replay_can_be_disabled() -> None:
    bus = EventBus()
    await bus.publish(topics.FLIGHT_BATTERY, {"pct": 50})
    sub = bus.subscribe("*", replay_last=False)
    await bus.publish(topics.PERSON_DETECTED)
    event = await asyncio.wait_for(sub.get(), timeout=1)
    assert event.topic == topics.PERSON_DETECTED


async def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    sub = bus.subscribe("*")
    await bus.publish(topics.PERSON_DETECTED)
    bus.unsubscribe(sub)
    await bus.publish(topics.PERSON_DOWN)  # after close: not delivered
    assert bus.subscriber_count == 0

    event = await sub.get()  # queued-before-close event still readable
    assert event.topic == topics.PERSON_DETECTED
    with pytest.raises(EventBusClosedError):
        await sub.get()


async def test_async_iteration_ends_on_close() -> None:
    bus = EventBus()
    sub = bus.subscribe("person.*")
    await bus.publish(topics.PERSON_DETECTED)
    await bus.publish(topics.PERSON_DOWN)
    sub.close()
    seen = [event.topic async for event in sub]
    assert seen == [topics.PERSON_DETECTED, topics.PERSON_DOWN]


async def test_concurrent_publishers() -> None:
    bus = EventBus()
    sub = bus.subscribe("*")
    tasks = 10
    per_task = 20

    async def blast(n: int) -> None:
        for i in range(per_task):
            await bus.publish(topics.UTTERANCE_HEARD, {"task": n, "i": i})

    await asyncio.gather(*(blast(n) for n in range(tasks)))

    events = [await asyncio.wait_for(sub.get(), timeout=1) for _ in range(tasks * per_task)]
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)  # delivered in publish order
    assert len(set(seqs)) == tasks * per_task  # every event exactly once
    # every (task, i) pair arrived
    pairs = {(e.payload["task"], e.payload["i"]) for e in events}
    assert len(pairs) == tasks * per_task


async def test_publish_with_no_subscribers_is_safe() -> None:
    bus = EventBus()
    event = await bus.publish(topics.CHECKIN_DUE)
    assert event.seq == 1
    assert bus.last(topics.CHECKIN_DUE) is not None
    assert bus.last(topics.PERSON_DOWN) is None


async def test_subscribe_requires_pattern() -> None:
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.subscribe()


def test_topic_matches() -> None:
    assert topics.topic_matches("person.*", topics.PERSON_DOWN)
    assert topics.topic_matches("*", topics.DOCK_CAPTURED)
    assert topics.topic_matches(topics.PERSON_DOWN, topics.PERSON_DOWN)
    assert not topics.topic_matches("person.*", topics.FLIGHT_LANDED)
    assert topics.PERSON_DOWN in topics.ALL_TOPICS
