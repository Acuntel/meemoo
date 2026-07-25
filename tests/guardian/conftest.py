"""Guardian test fixtures: real SQLite schema, fake clock, recording stubs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from meemoo.core.bus import EventBus
from meemoo.core.db import create_all, make_engine
from meemoo.core.models import Contact, Device, Person
from meemoo.guardian.machine import EscalationMachine, GuardianConfig, State
from meemoo.guardian.notifier import SimulatedNotifier
from meemoo.guardian.service import GuardianService


def mstate(machine: EscalationMachine) -> State:
    """Fresh read of the machine state (defeats mypy literal-narrowing
    across mutating calls, so sequential state asserts type-check)."""
    return machine.state


class FakeClock:
    """Deterministic monotonic clock the tests advance by hand."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class SpeakRecorder:
    """Records every line the guardian speaks."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    async def __call__(self, line: str) -> None:
        self.lines.append(line)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = make_engine(tmp_path / "guardian.db")
    create_all(eng)
    return eng


@pytest.fixture
def db_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def seeded(db_factory: sessionmaker[Session]) -> dict[str, int]:
    """A device, its person, and two ordered contacts (daughter, then son)."""
    with db_factory() as db:
        device = Device(name="Meemoo One")
        db.add(device)
        db.flush()
        person = Person(device_id=device.id, name="Ruth", room="bedroom")
        daughter = Contact(
            device_id=device.id, order_index=0, name="Dana",
            relationship_label="daughter", phone="+13125550100",
            notify_sms=True, notify_call=True,
        )
        son = Contact(
            device_id=device.id, order_index=1, name="Sam",
            relationship_label="son", phone="+13125550101",
            notify_sms=True, notify_call=False,
        )
        db.add_all([person, daughter, son])
        db.commit()
        return {
            "device_id": device.id, "person_id": person.id,
            "daughter_id": daughter.id, "son_id": son.id,
        }


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def speaker() -> SpeakRecorder:
    return SpeakRecorder()


@pytest.fixture
def notifier(bus: EventBus) -> SimulatedNotifier:
    return SimulatedNotifier(bus)


ServiceFactory = Callable[..., GuardianService]


@pytest.fixture
def make_service(
    bus: EventBus,
    db_factory: sessionmaker[Session],
    seeded: dict[str, int],
    clock: FakeClock,
    speaker: SpeakRecorder,
    notifier: SimulatedNotifier,
) -> ServiceFactory:
    """Fully-wired GuardianService on a fake clock (not started — tests drive)."""

    def _make(**overrides: object) -> GuardianService:
        kwargs: dict[str, object] = {
            "device_id": seeded["device_id"],
            "config": GuardianConfig(),
            "notifier": notifier,
            "speak": speaker,
            "clock": clock,
            "test_number": "+13125550199",
        }
        kwargs.update(overrides)
        return GuardianService(bus, db_factory, **kwargs)  # type: ignore[arg-type]

    return _make


class BusRecorder:
    """Collects every event published on the bus for assertions."""

    def __init__(self, bus: EventBus) -> None:
        self._sub = bus.subscribe("*", replay_last=False)
        self.events: list[tuple[str, dict[str, object]]] = []

    async def drain(self) -> list[tuple[str, dict[str, object]]]:
        while not self._sub._queue.empty():  # test-only peek
            event = await self._sub.get()
            self.events.append((event.topic, event.payload))
        return self.events

    def topics(self) -> list[str]:
        return [t for t, _ in self.events]


@pytest.fixture
def recorder(bus: EventBus) -> BusRecorder:
    return BusRecorder(bus)


Speak = Callable[[str], Awaitable[None]]
