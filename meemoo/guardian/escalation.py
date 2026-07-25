"""Alert rows, contact fan-out, acknowledgment, false-alarm counter.

The DB side of an escalation episode. Alerts open at L1 (per data model), the
level bumps as the ladder climbs, and acknowledgment records WHO acked, WHEN,
and the LATENCY from open — the exact fields research 03 §C.2 says decide a
failure-to-escalate case ("notified daughter 14s after event, delivered,
unacknowledged 47 min").

False-alarms-per-week (Constitution Art. VIII §3 — a published headline
number, not a buried stat) counts ``guardian.false_alarm`` rows in the
append-only events table over the trailing 7 days.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from meemoo.core.models import Alert
from meemoo.core.models import Event as EventRow
from meemoo.core.versioning import get_versions
from meemoo.guardian.contacts import list_contacts
from meemoo.guardian.notifier import Notification, Notifier, NotifyResult

logger = logging.getLogger(__name__)

FALSE_ALARM_EVENT = "guardian.false_alarm"

SMS_TEMPLATE = (
    "MEEMOO ALERT ({level}): possible emergency — {reason}. "
    "Reply ACK to acknowledge and halt escalation."
)
CALL_TEMPLATE = (
    "This is Meemoo with a {level} alert. {reason}. "
    "Please check on them, or acknowledge from the dashboard."
)


def open_alert(
    db: Session, *, device_id: int, reason: str, evidence_event_id: int | None = None
) -> Alert:
    """Open the episode's alert row at L1, stamped with active versions."""
    versions = get_versions()
    alert = Alert(
        device_id=device_id,
        level="L1",
        state="open",
        reason=reason[:200],
        evidence_event_id=evidence_event_id,
        model_version=versions.get("model"),
        prompt_version=versions.get("prompt"),
        threshold_version=versions.get("threshold"),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def bump_alert(db: Session, alert_id: int, level: str) -> None:
    alert = db.get(Alert, alert_id)
    if alert is not None:
        alert.level = level
        db.commit()


def ack_alert(
    db: Session, alert_id: int, *, contact_id: int | None, via: str
) -> tuple[Alert | None, float | None]:
    """Mark acknowledged; returns (alert, latency_s from open). Idempotent."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        return None, None
    if alert.acknowledged_at is not None:
        latency = (alert.acknowledged_at - alert.opened_at).total_seconds()
        return alert, latency
    now = datetime.now(UTC).replace(tzinfo=None)
    alert.acknowledged_at = now
    alert.acknowledged_by_contact_id = contact_id
    alert.state = f"acknowledged:{via}"
    db.commit()
    latency = (now - alert.opened_at).total_seconds()
    return alert, latency


def close_alert(db: Session, alert_id: int, state: str) -> None:
    alert = db.get(Alert, alert_id)
    if alert is not None and alert.acknowledged_at is None:
        alert.state = state
        db.commit()


def latest_open_alert(db: Session, device_id: int) -> Alert | None:
    return (
        db.query(Alert)
        .filter(Alert.device_id == device_id, Alert.state == "open")
        .order_by(Alert.id.desc())
        .first()
    )


def record_false_alarm(db: Session, *, device_id: int, detail: dict[str, object]) -> EventRow:
    """Append a false-alarm event row (feeds the Art. VIII §3 headline)."""
    row = EventRow(device_id=device_id, type=FALSE_ALARM_EVENT, payload=detail)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def false_alarms_per_week(db: Session, device_id: int | None = None) -> int:
    """False alarms in the trailing 7 days (the published headline number)."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    query = db.query(EventRow).filter(
        EventRow.type == FALSE_ALARM_EVENT, EventRow.ts >= cutoff
    )
    if device_id is not None:
        query = query.filter(EventRow.device_id == device_id)
    return int(query.count())


async def notify_level(
    notifier: Notifier,
    db: Session | None,
    *,
    device_id: int,
    level: str,
    reason: str,
    alert_id: int | None,
    test_number: str | None = None,
) -> list[tuple[Notification, NotifyResult]]:
    """Fan out one escalation level to its recipients per their prefs.

    L1 → the primary (first) contact; L2 → every remaining contact;
    L3 → the configured TEST number (never 911 — Art. IV §1).
    No contacts / no DB is logged and survived, never raised (Art. IX §3).
    """
    recipients: list[tuple[str, str | None, bool, bool]] = []  # phone, name, sms, call
    if level == "L3":
        if test_number:
            recipients = [(test_number, "test number", False, True)]
    elif db is not None:
        contacts = list_contacts(db, device_id)
        chosen = contacts[:1] if level == "L1" else contacts[1:] or contacts
        recipients = [
            (c.phone, c.name, c.notify_sms, c.notify_call) for c in chosen if c.phone
        ]
    if not recipients:
        logger.warning(
            "escalation has no reachable recipients",
            extra={"fields": {"level": level, "device_id": device_id}},
        )
        return []

    results: list[tuple[Notification, NotifyResult]] = []
    for phone, name, wants_sms, wants_call in recipients:
        channels: list[str] = []
        if wants_sms:
            channels.append("sms")
        if wants_call:
            channels.append("call")
        for channel in channels or ["sms"]:
            template = SMS_TEMPLATE if channel == "sms" else CALL_TEMPLATE
            notification = Notification(
                channel="sms" if channel == "sms" else "call",
                to=phone,
                body=template.format(level=level, reason=reason),
                level=level,
                contact_name=name,
                alert_id=alert_id,
            )
            result = await notifier.send(notification)
            results.append((notification, result))
    return results
