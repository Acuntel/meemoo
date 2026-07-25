"""GuardianService integration: bus in, effects out, audit rows immutable."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session, sessionmaker

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.models import Alert, AuditLog, verify_audit_chain
from meemoo.core.models import Event as EventRow
from meemoo.guardian.machine import GuardianConfig, State
from meemoo.guardian.notifier import SimulatedNotifier, make_notifier
from meemoo.guardian.service import CHECKIN_GREETING, VERIFY_PROMPT, GuardianService
from tests.guardian.conftest import (
    BusRecorder,
    FakeClock,
    ServiceFactory,
    SpeakRecorder,
    mstate,
)


async def walk_to_l1(service: GuardianService, clock: FakeClock) -> None:
    """fake person.down → verify (2 asks) → no response → L1."""
    await service.handle_event(topics.PERSON_DOWN, {"t": clock(), "ballistic": True})
    cfg = service.machine.config
    clock.advance(cfg.verify_ask_timeout_s)
    await service.tick()
    clock.advance(cfg.verify_ask_timeout_s)
    await service.tick()
    assert mstate(service.machine) is State.ESCALATE_L1


async def test_person_down_flies_and_asks_twice(
    make_service: ServiceFactory, clock: FakeClock, speaker: SpeakRecorder,
    recorder: BusRecorder,
) -> None:
    service = make_service()
    await service.handle_event(topics.PERSON_DOWN, {"t": clock()})
    assert mstate(service.machine) is State.CONCERN
    assert speaker.lines == [VERIFY_PROMPT]
    clock.advance(service.machine.config.verify_ask_timeout_s)
    await service.tick()
    assert speaker.lines == [VERIFY_PROMPT, VERIFY_PROMPT]  # asked exactly twice
    await recorder.drain()
    dispatches = [p for t, p in recorder.events if t == topics.FLIGHT_DISPATCH]
    assert dispatches and dispatches[0]["reason"] == "verify"
    assert topics.GUARDIAN_STATE in recorder.topics()


async def test_l1_opens_alert_and_notifies_primary_contact(
    make_service: ServiceFactory, clock: FakeClock, notifier: SimulatedNotifier,
    db_factory: sessionmaker[Session], seeded: dict[str, int], recorder: BusRecorder,
) -> None:
    service = make_service()
    await walk_to_l1(service, clock)
    # alert row open at L1 with evidence + version columns present
    with db_factory() as db:
        alert = db.query(Alert).one()
        assert alert.level == "L1" and alert.state == "open"
        assert alert.evidence_event_id is not None
        evidence = db.get(EventRow, alert.evidence_event_id)
        assert evidence is not None and evidence.type == topics.PERSON_DOWN
    # primary contact (Dana) got SMS + call; son not yet
    tos = {n.to for n in notifier.sent}
    assert tos == {"+13125550100"}
    assert {n.channel for n in notifier.sent} == {"sms", "call"}
    await recorder.drain()
    assert topics.ESCALATION_L1 in recorder.topics()


async def test_timeout_ladder_l2_l3_notifications(
    make_service: ServiceFactory, clock: FakeClock, notifier: SimulatedNotifier,
    db_factory: sessionmaker[Session], recorder: BusRecorder,
) -> None:
    service = make_service()
    await walk_to_l1(service, clock)
    cfg = service.machine.config
    clock.advance(cfg.l1_ack_timeout_s)
    await service.tick()
    assert mstate(service.machine) is State.ESCALATE_L2
    # L2 notifies the remaining contact (Sam, sms only)
    sam = [n for n in notifier.sent if n.to == "+13125550101"]
    assert sam and {n.channel for n in sam} == {"sms"}
    clock.advance(cfg.l2_ack_timeout_s)
    await service.tick()
    assert mstate(service.machine) is State.ESCALATE_L3
    # L3 rings the TEST number — full-screen alert on the bus, never 911
    ring = [n for n in notifier.sent if n.to == "+13125550199"]
    assert ring and ring[0].channel == "call"
    await recorder.drain()
    l3 = [p for t, p in recorder.events if t == topics.ESCALATION_L3]
    assert l3 and l3[0]["full_screen_alert"] is True
    with db_factory() as db:
        assert db.query(Alert).one().level == "L3"


async def test_ack_halts_escalation_and_logs_who_when_latency(
    make_service: ServiceFactory, clock: FakeClock, seeded: dict[str, int],
    db_factory: sessionmaker[Session], recorder: BusRecorder,
) -> None:
    service = make_service()
    await walk_to_l1(service, clock)
    result = await service.acknowledge(contact_id=seeded["daughter_id"], via="dashboard")
    assert result["state"] == "IDLE"
    assert mstate(service.machine) is State.IDLE
    # ladder is dead: no L2 even long after
    clock.advance(10_000.0)
    await service.tick()
    assert mstate(service.machine) is State.IDLE
    with db_factory() as db:
        alert = db.query(Alert).one()
        assert alert.state == "acknowledged:dashboard"
        assert alert.acknowledged_by_contact_id == seeded["daughter_id"]
        assert alert.acknowledged_at is not None
        ack_rows = db.query(AuditLog).filter(AuditLog.action == "guardian.acknowledged").all()
        assert len(ack_rows) == 1
        detail = json.loads(ack_rows[0].detail or "{}")
        assert detail["contact_id"] == seeded["daughter_id"]
        assert detail["latency_s"] is not None and detail["latency_s"] >= 0
    await recorder.drain()
    assert topics.ESCALATION_ACKNOWLEDGED in recorder.topics()


async def test_distress_bus_event_goes_straight_to_l1(
    make_service: ServiceFactory, notifier: SimulatedNotifier,
    db_factory: sessionmaker[Session],
) -> None:
    service = make_service()
    await service.handle_event(
        topics.DISTRESS_HEARD, {"phrase": "help me", "transcript": "help me please"}
    )
    assert mstate(service.machine) is State.ESCALATE_L1
    assert notifier.sent  # contacts notified immediately, no verify loop
    with db_factory() as db:
        alert = db.query(Alert).one()
        assert alert.reason == "distress phrase heard"
        assert alert.evidence_event_id is not None


async def test_checkin_speaks_greeting_and_voice_reply_resolves(
    make_service: ServiceFactory, clock: FakeClock, speaker: SpeakRecorder,
    db_factory: sessionmaker[Session],
) -> None:
    service = make_service()
    await service.handle_event(topics.CHECKIN_DUE, {"time": "09:00"})
    assert mstate(service.machine) is State.CHECKING
    assert speaker.lines == [CHECKIN_GREETING]
    await service.handle_event(topics.UTTERANCE_HEARD, {"transcript": "doing fine dear"})
    assert mstate(service.machine) is State.IDLE
    with db_factory() as db:
        ok_rows = db.query(AuditLog).filter(AuditLog.action == "guardian.person_ok").all()
        assert ok_rows


async def test_false_alarm_counter_counts_verify_resolved_episodes(
    make_service: ServiceFactory, clock: FakeClock,
) -> None:
    service = make_service()
    assert service.false_alarms_per_week() == 0
    await service.handle_event(topics.PERSON_DOWN, {"t": clock()})
    await service.handle_event(topics.UTTERANCE_HEARD, {"transcript": "i'm fine"})
    assert mstate(service.machine) is State.IDLE
    assert service.false_alarms_per_week() == 1


async def test_audit_rows_complete_and_immutable(
    make_service: ServiceFactory, clock: FakeClock, db_factory: sessionmaker[Session],
    seeded: dict[str, int],
) -> None:
    service = make_service()
    await walk_to_l1(service, clock)
    await service.acknowledge(contact_id=seeded["daughter_id"])
    with db_factory() as db:
        transitions = (
            db.query(AuditLog).filter(AuditLog.action == "guardian.transition")
            .order_by(AuditLog.id).all()
        )
        walk = [(r.from_state, r.to_state) for r in transitions]
        assert walk == [
            ("IDLE", "CONCERN"),
            ("CONCERN", "CONCERN"),
            ("CONCERN", "ESCALATE_L1"),
            ("ESCALATE_L1", "IDLE"),
        ]
        assert all(r.trigger for r in transitions)
        assert all(r.actor == "guardian" for r in transitions)
        # notify attempts audited with delivery detail
        notifies = db.query(AuditLog).filter(AuditLog.action == "guardian.notify").all()
        assert notifies and all(
            json.loads(r.detail or "{}")["delivered"] is True for r in notifies
        )
        # the chain verifies, and the rows physically reject UPDATE
        ok, bad = verify_audit_chain(db)
        assert ok and bad is None
        with pytest.raises(DatabaseError):
            db.execute(text("UPDATE audit_log SET detail='tampered' WHERE id=1"))
            db.commit()


async def test_zero_creds_uses_simulated_notifier_without_error(
    bus: EventBus, bare_settings: object, clock: FakeClock,
) -> None:
    """No Twilio, no DB, no voice — the spine still walks to L3 (Art. IX §3)."""
    from meemoo.core.config import Settings

    assert isinstance(bare_settings, Settings)
    notifier = make_notifier(bare_settings, bus)
    assert isinstance(notifier, SimulatedNotifier)
    service = GuardianService(bus, None, notifier=notifier, clock=clock)
    await service.handle_event(topics.PERSON_DOWN, {"t": 0.0})
    cfg = service.machine.config
    for step in (cfg.verify_ask_timeout_s, cfg.verify_ask_timeout_s,
                 cfg.l1_ack_timeout_s, cfg.l2_ack_timeout_s):
        clock.advance(step)
        await service.tick()
    assert mstate(service.machine) is State.ESCALATE_L3
    assert service.false_alarms_per_week() is None  # no DB — honest, not fake zero


async def test_other_devices_events_are_ignored(
    make_service: ServiceFactory, clock: FakeClock,
) -> None:
    service = make_service()
    await service.handle_event(topics.PERSON_DOWN, {"device_id": 999})
    assert mstate(service.machine) is State.IDLE


async def test_started_service_reacts_to_bus_and_stops_cleanly(
    make_service: ServiceFactory, bus: EventBus,
) -> None:
    import asyncio

    service = make_service(tick_interval_s=0.01)
    await service.start()
    try:
        await bus.publish(topics.PERSON_DOWN, {"t": 1.0})
        await asyncio.sleep(0.05)
        assert mstate(service.machine) is State.CONCERN
    finally:
        await service.stop()


async def test_l3_with_auto911_flag_rings_test_number_only(
    make_service: ServiceFactory, clock: FakeClock, notifier: SimulatedNotifier,
) -> None:
    """Art. IV §1: even with the flag forced on, nothing but the TEST number."""
    service = make_service(config=GuardianConfig(auto_dial_911=True))
    await walk_to_l1(service, clock)
    clock.advance(service.machine.config.l1_ack_timeout_s)
    await service.tick()
    clock.advance(service.machine.config.l2_ack_timeout_s)
    await service.tick()
    assert mstate(service.machine) is State.ESCALATE_L3
    destinations = {n.to for n in notifier.sent}
    assert "911" not in destinations
    assert all(not n.to.endswith("911") for n in notifier.sent)
