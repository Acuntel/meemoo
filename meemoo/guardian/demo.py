"""Guardian demo: simulated fall → verify asks → L1 → ack, fully headless.

Run: ``uv run python -m meemoo.guardian.demo`` (or ``make demo-guardian``).
Zero credentials, in-memory DB, simulated notifier, NullTTS voice — the
whole escalation spine end to end on a laptop (Art. IX §3/§5). Pass
``--no-ack`` to watch the ladder climb all the way to L3 instead.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy.orm import sessionmaker

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.db import create_all, make_engine
from meemoo.core.logging import setup_logging
from meemoo.core.models import Contact, Device, Person
from meemoo.guardian.machine import GuardianConfig, State
from meemoo.guardian.notifier import SimulatedNotifier
from meemoo.guardian.service import GuardianService

logger = logging.getLogger(__name__)


def _state(service: GuardianService) -> State:
    """Fresh state read (avoids mypy literal-narrowing across awaits)."""
    return service.machine.state

# Short demo timings — the committed GuardianConfig defaults stay untouched.
DEMO_CONFIG = GuardianConfig(
    checkin_response_timeout_s=2.0,
    verify_ask_timeout_s=1.0,
    l1_ack_timeout_s=2.0,
    l2_ack_timeout_s=2.0,
)


async def run_demo(ack: bool) -> None:
    bus = EventBus()
    engine = make_engine(":memory:")
    create_all(engine)
    db_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with db_factory() as db:
        device = Device(name="Demo Meemoo")
        db.add(device)
        db.flush()
        db.add_all([
            Person(device_id=device.id, name="Ruth", room="bedroom"),
            Contact(device_id=device.id, order_index=0, name="Dana",
                    relationship_label="daughter", phone="+13125550100"),
            Contact(device_id=device.id, order_index=1, name="Sam",
                    relationship_label="son", phone="+13125550101", notify_call=False),
        ])
        db.commit()
        device_id = device.id

    notifier = SimulatedNotifier(bus)

    async def speak(line: str) -> None:
        logger.info("MEEMOO SAYS: %s", line)

    service = GuardianService(
        bus, db_factory, device_id=device_id, config=DEMO_CONFIG,
        notifier=notifier, speak=speak, test_number="+13125550199",
        tick_interval_s=0.1,
    )

    watcher = bus.subscribe(topics.GUARDIAN_STATE, "escalation.*", replay_last=False)

    async def watch() -> None:
        async for event in watcher:
            logger.info("bus: %s %s", event.topic, event.payload)

    watch_task = asyncio.create_task(watch())
    await service.start()
    try:
        logger.info("--- simulated fall (perception would publish this at 15 s) ---")
        await bus.publish(topics.PERSON_DOWN, {"device_id": device_id, "ballistic": True})
        await asyncio.sleep(DEMO_CONFIG.verify_ask_timeout_s * 2 + 0.5)
        assert _state(service) is State.ESCALATE_L1, _state(service)
        logger.info("--- L1 reached; %d simulated notifications sent ---",
                    len(notifier.sent))
        if ack:
            result = await service.acknowledge(via="demo-dashboard")
            logger.info("--- acknowledged: %s ---", result)
            assert _state(service) is State.IDLE
        else:
            await asyncio.sleep(DEMO_CONFIG.l1_ack_timeout_s
                                + DEMO_CONFIG.l2_ack_timeout_s + 0.5)
            assert _state(service) is State.ESCALATE_L3, _state(service)
            logger.info("--- L3: test number rung, full-screen alert (never 911) ---")
        falses = service.false_alarms_per_week()
        logger.info("--- false alarms this week: %s ---", falses)
    finally:
        await service.stop()
        watcher.close()
        watch_task.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-ack", action="store_true",
                        help="let the ladder climb to L3 instead of acking at L1")
    args = parser.parse_args()
    setup_logging(json_output=False, level="INFO")
    asyncio.run(run_demo(ack=not args.no_ack))


if __name__ == "__main__":
    main()
