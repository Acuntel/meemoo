"""Session tests: 45 s close, rolling context, transcript toggle (Art. V §2)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.db import create_all, make_engine
from meemoo.core.models import Conversation, Device, Message
from meemoo.voice.disclosure import REDISCLOSURE_LINE
from meemoo.voice.session import ROLLING_CONTEXT_MAX, SessionManager

from .conftest import FakeClock


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = make_engine(tmp_path / "test.db")
    create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_factory(engine: Engine) -> sessionmaker[DbSession]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def _mk_device(db_factory: sessionmaker[DbSession], *, store: bool) -> int:
    with db_factory() as db:
        device = Device(name="test", store_transcripts=store)
        db.add(device)
        db.commit()
        return int(device.id)


async def test_open_close_and_bus_events(
    bus: EventBus, db_factory: sessionmaker[DbSession], clock: FakeClock
) -> None:
    device_id = _mk_device(db_factory, store=True)
    sub = bus.subscribe("voice.*")
    manager = SessionManager(bus, db_factory, clock=clock)
    session, line = await manager.open(device_id, trigger="ptt")
    assert line  # disclosure line returned to be spoken
    opened = await sub.get()
    assert opened.topic == topics.VOICE_SESSION_OPENED
    await manager.close(reason="test")
    closed = await sub.get()
    assert closed.topic == topics.VOICE_SESSION_CLOSED
    with db_factory() as db:
        row = db.get(Conversation, session.conversation_row_id)
        assert row is not None and row.ended_at is not None


async def test_silence_closes_session_after_45s(
    bus: EventBus, clock: FakeClock
) -> None:
    manager = SessionManager(bus, None, silence_close_s=45.0, clock=clock)
    await manager.open(1, trigger="ptt")
    clock.advance(44.0)
    await manager.tick()
    assert manager.active is not None  # still open at 44 s
    manager.add_user("still here")  # activity resets the timer
    clock.advance(44.0)
    await manager.tick()
    assert manager.active is not None
    clock.advance(45.0)
    await manager.tick()
    assert manager.active is None  # closed by silence


async def test_periodic_redisclosure_via_tick(bus: EventBus, clock: FakeClock) -> None:
    manager = SessionManager(bus, None, silence_close_s=10_000.0, clock=clock)
    await manager.open(1, trigger="ptt")
    clock.advance(601.0)
    manager.add_user("keeping the session alive")
    line = await manager.tick()
    assert line == REDISCLOSURE_LINE
    line2 = await manager.tick()
    assert line2 is None  # timer reset — not spoken again immediately


async def test_transcripts_persisted_when_toggle_on(
    bus: EventBus, db_factory: sessionmaker[DbSession], clock: FakeClock
) -> None:
    device_id = _mk_device(db_factory, store=True)
    manager = SessionManager(bus, db_factory, clock=clock)
    session, _line = await manager.open(device_id, trigger="checkin")
    manager.add_user("hello meemoo")
    manager.add_assistant("hello ruth")
    with db_factory() as db:
        rows = db.scalars(
            select(Message).where(Message.conversation_id == session.conversation_row_id)
        ).all()
    contents = [(r.role, r.content) for r in rows]
    assert ("user", "hello meemoo") in contents
    assert ("assistant", "hello ruth") in contents
    # text only — the Message model has no audio column at all (Art. V §2)
    assert not hasattr(Message, "audio")


async def test_transcripts_not_persisted_when_toggle_off(
    bus: EventBus, db_factory: sessionmaker[DbSession], clock: FakeClock
) -> None:
    device_id = _mk_device(db_factory, store=False)
    manager = SessionManager(bus, db_factory, clock=clock)
    session, _line = await manager.open(device_id, trigger="ptt")
    manager.add_user("this must not be stored")
    assert session.store_transcripts is False
    assert session.conversation_row_id is None  # not even a conversation row
    with db_factory() as db:
        assert db.scalars(select(Message)).all() == []
    # the rolling in-memory context still works for the live conversation
    assert any(m["content"] == "this must not be stored" for m in session.context)


async def test_rolling_context_is_capped(bus: EventBus, clock: FakeClock) -> None:
    manager = SessionManager(bus, None, clock=clock)
    session, _line = await manager.open(1, trigger="ptt")
    for i in range(ROLLING_CONTEXT_MAX + 20):
        manager.add_user(f"message {i}")
    assert len(session.context) == ROLLING_CONTEXT_MAX


async def test_no_db_runs_memory_only(bus: EventBus, clock: FakeClock) -> None:
    manager = SessionManager(bus, None, clock=clock)  # no DB factory: never crashes
    session, _line = await manager.open(1, trigger="ptt")
    manager.add_user("hi")
    assert session.store_transcripts is True  # default ON
    assert session.conversation_row_id is None
    await manager.close()
