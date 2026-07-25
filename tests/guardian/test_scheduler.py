"""Check-in scheduler: default times, DB overrides, fire → checkin.due."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.models import CheckinSchedule
from meemoo.guardian.scheduler import DEFAULT_CHECKIN_TIMES, CheckinScheduler


def test_default_times_are_9a_1p_6p_9p() -> None:
    assert DEFAULT_CHECKIN_TIMES == ("09:00", "13:00", "18:00", "21:00")


def test_load_times_defaults_without_db(bus: EventBus) -> None:
    scheduler = CheckinScheduler(bus, None)
    assert scheduler.load_times() == [(t, None) for t in DEFAULT_CHECKIN_TIMES]


def test_load_times_prefers_enabled_db_rows(
    bus: EventBus, db_factory: sessionmaker[Session], seeded: dict[str, int]
) -> None:
    device_id = seeded["device_id"]
    with db_factory() as db:
        db.add_all([
            CheckinSchedule(device_id=device_id, time_of_day="08:30", label="morning"),
            CheckinSchedule(device_id=device_id, time_of_day="20:15", label="evening"),
            CheckinSchedule(device_id=device_id, time_of_day="12:00", enabled=False),
        ])
        db.commit()
    scheduler = CheckinScheduler(bus, db_factory, device_id=device_id)
    assert scheduler.load_times() == [("08:30", "morning"), ("20:15", "evening")]


async def test_cron_jobs_registered_for_each_time(bus: EventBus) -> None:
    scheduler = CheckinScheduler(bus, None)
    aps = scheduler.start(paused=True)
    try:
        jobs = aps.get_jobs()
        assert len(jobs) == len(DEFAULT_CHECKIN_TIMES)
        ids = {job.id for job in jobs}
        assert ids == {f"checkin-1-{t}" for t in DEFAULT_CHECKIN_TIMES}
        # cron fields carry the configured hours
        hours: set[str] = set()
        for job in jobs:
            for field in job.trigger.fields:
                if field.name == "hour":
                    hours.add(str(field))
        assert hours == {"9", "13", "18", "21"}
    finally:
        scheduler.stop()


async def test_fire_publishes_checkin_due(bus: EventBus) -> None:
    scheduler = CheckinScheduler(bus, None, device_id=4)
    sub = bus.subscribe(topics.CHECKIN_DUE, replay_last=False)
    await scheduler.fire("09:00", "morning round")
    event = await sub.get()
    assert event.payload == {"device_id": 4, "time": "09:00", "label": "morning round"}
