"""Check-in scheduler (APScheduler): fires ``checkin.due`` per device.

Default times 9a / 1p / 6p / 9p (MASTER_PROMPT §4); per-device overrides come
from ``checkin_schedule`` rows. A check-in = sim round + REAL voice check-in
— the GuardianService owns both once it receives ``checkin.due``; this module
only keeps time. ``fire()`` is public so tests (and the demo) trigger a
check-in deterministically without waiting for a cron edge.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session, sessionmaker

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.models import CheckinSchedule

logger = logging.getLogger(__name__)

DEFAULT_CHECKIN_TIMES: tuple[str, ...] = ("09:00", "13:00", "18:00", "21:00")


class CheckinScheduler:
    """Loads per-device times and publishes ``checkin.due`` on schedule."""

    def __init__(
        self,
        bus: EventBus,
        db_factory: sessionmaker[Session] | None = None,
        *,
        device_id: int = 1,
    ) -> None:
        self._bus = bus
        self._db_factory = db_factory
        self.device_id = device_id
        self._scheduler: AsyncIOScheduler | None = None

    def load_times(self) -> list[tuple[str, str | None]]:
        """Enabled (time, label) pairs from the DB; defaults when none exist."""
        if self._db_factory is not None:
            with self._db_factory() as db:
                rows = (
                    db.query(CheckinSchedule)
                    .filter(
                        CheckinSchedule.device_id == self.device_id,
                        CheckinSchedule.enabled.is_(True),
                    )
                    .order_by(CheckinSchedule.time_of_day.asc())
                    .all()
                )
            if rows:
                return [(row.time_of_day, row.label) for row in rows]
        return [(t, None) for t in DEFAULT_CHECKIN_TIMES]

    def start(self, *, paused: bool = False) -> AsyncIOScheduler:
        """Register cron jobs and start the scheduler (idempotent)."""
        if self._scheduler is not None:
            return self._scheduler
        scheduler = AsyncIOScheduler()
        for time_of_day, label in self.load_times():
            hour, _, minute = time_of_day.partition(":")
            scheduler.add_job(
                self.fire,
                CronTrigger(hour=int(hour), minute=int(minute or 0)),
                args=[time_of_day, label],
                id=f"checkin-{self.device_id}-{time_of_day}",
                replace_existing=True,
            )
        scheduler.start(paused=paused)
        self._scheduler = scheduler
        logger.info(
            "check-in scheduler started",
            extra={"fields": {"device_id": self.device_id,
                              "times": [t for t, _ in self.load_times()]}},
        )
        return scheduler

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def reschedule(self) -> list[str]:
        """Re-read the DB and retune cron jobs — called on schedule edits.

        Returns the active times so the API can echo them. No-op (returns the
        would-be times) when the scheduler isn't running.
        """
        times = self.load_times()
        if self._scheduler is not None:
            for job in self._scheduler.get_jobs():
                if job.id.startswith(f"checkin-{self.device_id}-"):
                    job.remove()
            for time_of_day, label in times:
                hour, _, minute = time_of_day.partition(":")
                self._scheduler.add_job(
                    self.fire,
                    CronTrigger(hour=int(hour), minute=int(minute or 0)),
                    args=[time_of_day, label],
                    id=f"checkin-{self.device_id}-{time_of_day}",
                    replace_existing=True,
                )
            logger.info(
                "check-in scheduler retuned",
                extra={"fields": {"device_id": self.device_id,
                                  "times": [t for t, _ in times]}},
            )
        return [t for t, _ in times]

    async def fire(self, time_of_day: str = "manual", label: str | None = None) -> None:
        """Publish ``checkin.due`` now (cron target + deterministic test/demo entry)."""
        logger.info(
            "check-in due",
            extra={"fields": {"device_id": self.device_id, "time": time_of_day,
                              "label": label}},
        )
        await self._bus.publish(
            topics.CHECKIN_DUE,
            {"device_id": self.device_id, "time": time_of_day, "label": label},
        )
