"""Research-credibility metric calculations (Constitution Art. VIII).

Pure read-model functions over the real tables. Where the product does not
yet generate a signal (reminder adherence needs the reminder engine), the
result is honestly empty — the labeled synthetic demo mode
(:mod:`meemoo.api.metrics_demo`) exists for demos, never silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from meemoo.core.models import Conversation, Event, Message

USER_TRIGGERS = ("ptt", "wake")


@dataclass(frozen=True, slots=True)
class DayEngagement:
    date: str
    sessions: int
    user_initiated: int
    minutes: float
    turns: int

    @property
    def user_share(self) -> float:
        return self.user_initiated / self.sessions if self.sessions else 0.0


def _day_range(days: int) -> list[str]:
    today = datetime.now(UTC).date()
    return [str(today - timedelta(days=offset)) for offset in range(days - 1, -1, -1)]


def engagement_series(db: Session, device_id: int, days: int = 42) -> list[DayEngagement]:
    """Per-day sessions / user-initiated share / minutes / turns (Art. VIII §1)."""
    start = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    rows = (
        db.query(Conversation)
        .filter(Conversation.device_id == device_id, Conversation.started_at >= start)
        .all()
    )
    by_day: dict[str, list[Conversation]] = {}
    for row in rows:
        by_day.setdefault(str(row.started_at.date()), []).append(row)
    out: list[DayEngagement] = []
    for date in _day_range(days):
        day_rows = by_day.get(date, [])
        minutes = 0.0
        turns = 0
        for c in day_rows:
            if c.ended_at is not None:
                minutes += max(0.0, (c.ended_at - c.started_at).total_seconds() / 60.0)
            turns += (
                db.query(Message)
                .filter(Message.conversation_id == c.id, Message.role == "user")
                .count()
            )
        out.append(DayEngagement(
            date=date,
            sessions=len(day_rows),
            user_initiated=sum(1 for c in day_rows if c.trigger in USER_TRIGGERS),
            minutes=round(minutes, 1),
            turns=turns,
        ))
    return out


def _trend(values: list[float]) -> float:
    """Second-half mean minus first-half mean (positive = rising)."""
    active = [v for v in values]
    if len(active) < 4:
        return 0.0
    half = len(active) // 2
    first = sum(active[:half]) / half
    second = sum(active[half:]) / (len(active) - half)
    return second - first


def adherence_summary(db: Session, device_id: int, days: int = 28) -> dict[str, object]:
    """Reminder adherence from ``reminder.*`` events (research 07 §F.3).

    Honest empty until the reminder engine emits these events."""
    start = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    rows = (
        db.query(Event)
        .filter(
            Event.device_id == device_id,
            Event.type.like("reminder.%"),
            Event.ts >= start,
        )
        .all()
    )
    counts: dict[str, int] = {}
    prompts: list[int] = []
    for row in rows:
        state = row.type.split(".", 1)[1]
        counts[state] = counts.get(state, 0) + 1
        raw = row.payload.get("prompts")
        if isinstance(raw, int):
            prompts.append(raw)
    delivered = counts.get("delivered", 0)
    completed = counts.get("completed", 0)
    return {
        "window_days": days,
        "delivered": delivered,
        "acknowledged": counts.get("acknowledged", 0),
        "completed": completed,
        "missed": counts.get("missed", 0),
        "completion_rate": round(completed / delivered, 3) if delivered else None,
        "avg_prompts_required": round(sum(prompts) / len(prompts), 2) if prompts else None,
        "has_data": bool(rows),
    }


def human_contact_summary(db: Session, device_id: int, days: int = 28) -> dict[str, object]:
    """The anti-substitution metric (Art. VIII §4): logged calls/visits."""
    start = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    rows = (
        db.query(Event)
        .filter(
            Event.device_id == device_id,
            Event.type == "human_contact.logged",
            Event.ts >= start,
        )
        .all()
    )
    by_kind: dict[str, int] = {}
    weekly: dict[str, int] = {}
    for row in rows:
        kind = str(row.payload.get("kind", "other"))
        by_kind[kind] = by_kind.get(kind, 0) + 1
        week = row.ts.strftime("%G-W%V")
        weekly[week] = weekly.get(week, 0) + 1
    return {
        "window_days": days,
        "total": len(rows),
        "by_kind": by_kind,
        "weekly": [{"week": w, "count": c} for w, c in sorted(weekly.items())],
    }


def abandonment_composite(
    engagement: list[DayEngagement], adherence: dict[str, object]
) -> dict[str, object]:
    """Early-warning composite (Art. VIII §6): 0 (fine) → 100 (walking away)."""
    initiations = [float(d.user_initiated) for d in engagement]
    minutes = [d.minutes for d in engagement]
    risk = 0.0
    signals: list[str] = []
    if _trend(initiations) < 0:
        risk += 40.0
        signals.append("user-initiated sessions declining")
    if _trend(minutes) < 0:
        risk += 30.0
        signals.append("session length shortening")
    missed = adherence.get("missed", 0)
    delivered = adherence.get("delivered", 0)
    if (
        isinstance(missed, int)
        and isinstance(delivered, int)
        and delivered
        and missed / delivered > 0.25
    ):
        risk += 30.0
        signals.append("missed reminders rising")
    has_any = any(d.sessions for d in engagement)
    return {
        "risk": round(min(risk, 100.0)) if has_any else None,
        "signals": signals if has_any else [],
        "has_data": has_any,
    }
