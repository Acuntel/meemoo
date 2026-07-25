"""GuardianRecorder — the guardian's DB pen (evidence, audit, alerts).

Wraps the optional session factory so the service stays pure orchestration:
every write here is one short transaction, and a missing DB degrades to
logging-only without a crash (Art. IX §3). Audit rows go through
:func:`meemoo.core.models.audit.append_audit`, so they are hash-chained,
append-only, and version-stamped (research 03 §C.2).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, sessionmaker

from meemoo.core.models import Event as EventRow
from meemoo.core.models.audit import append_audit
from meemoo.guardian import escalation
from meemoo.guardian.notifier import Notification, Notifier, NotifyResult

logger = logging.getLogger(__name__)


class GuardianRecorder:
    """All guardian DB writes for one device; every method is None-DB safe."""

    def __init__(self, db_factory: sessionmaker[Session] | None, device_id: int) -> None:
        self._db_factory = db_factory
        self.device_id = device_id

    @property
    def has_db(self) -> bool:
        return self._db_factory is not None

    def record_evidence(self, topic: str, payload: dict[str, object]) -> int | None:
        """Append the triggering bus event to the events table; returns its id."""
        if self._db_factory is None:
            return None
        with self._db_factory() as db:
            row = EventRow(device_id=self.device_id, type=topic, payload=payload)
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id

    def audit(
        self,
        *,
        action: str,
        trigger: str | None,
        detail: str | None,
        from_state: str | None = None,
        to_state: str | None = None,
        evidence_event_id: int | None = None,
    ) -> None:
        """One immutable, hash-chained audit row."""
        if self._db_factory is None:
            return
        with self._db_factory() as db:
            append_audit(
                db, device_id=self.device_id, actor="guardian", action=action,
                from_state=from_state, to_state=to_state, trigger=trigger,
                evidence_event_id=evidence_event_id, detail=detail,
            )
            db.commit()

    def open_or_bump_alert(
        self, level: str, reason: str, *, alert_id: int | None, evidence_event_id: int | None
    ) -> int | None:
        """Open the episode alert at L1, or raise its level; returns alert id."""
        if self._db_factory is None:
            return alert_id
        with self._db_factory() as db:
            if level == "L1":
                alert = escalation.open_alert(
                    db, device_id=self.device_id, reason=reason,
                    evidence_event_id=evidence_event_id,
                )
                return alert.id
            if alert_id is not None:
                escalation.bump_alert(db, alert_id, level)
            return alert_id

    def close_alert(self, alert_id: int | None, state: str) -> None:
        if self._db_factory is None or alert_id is None:
            return
        with self._db_factory() as db:
            escalation.close_alert(db, alert_id, state)

    def ack_alert(
        self, alert_id: int, *, contact_id: int | None, via: str
    ) -> float | None:
        """Mark acknowledged; returns latency from open (None without a DB)."""
        if self._db_factory is None:
            return None
        with self._db_factory() as db:
            _, latency = escalation.ack_alert(db, alert_id, contact_id=contact_id, via=via)
            return latency

    def record_false_alarm(self, detail: dict[str, object]) -> None:
        if self._db_factory is None:
            return
        with self._db_factory() as db:
            escalation.record_false_alarm(db, device_id=self.device_id, detail=detail)

    def false_alarms_per_week(self) -> int | None:
        """The Art. VIII §3 headline number (None without a DB — never a fake 0)."""
        if self._db_factory is None:
            return None
        with self._db_factory() as db:
            return escalation.false_alarms_per_week(db, self.device_id)

    async def fan_out(
        self,
        notifier: Notifier | None,
        *,
        level: str,
        reason: str,
        alert_id: int | None,
        test_number: str | None,
    ) -> list[tuple[Notification, NotifyResult]]:
        """Notify the level's recipients per their prefs; empty if no notifier."""
        if notifier is None:
            logger.warning("no notifier configured — escalation logged only")
            return []
        if self._db_factory is None:
            return await escalation.notify_level(
                notifier, None, device_id=self.device_id, level=level,
                reason=reason, alert_id=alert_id, test_number=test_number,
            )
        with self._db_factory() as db:
            return await escalation.notify_level(
                notifier, db, device_id=self.device_id, level=level,
                reason=reason, alert_id=alert_id, test_number=test_number,
            )
