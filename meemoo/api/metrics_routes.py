"""Research-credibility REST (Art. VIII): every success metric, plus CSV export.

``?demo=true`` returns clearly-labeled synthetic data (``synthetic: true`` in
every payload) so the dashboard can be shown before weeks of real usage exist
— never silently mixed with real rows (research 07 §F.15).
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Query, Session

from meemoo.api import metrics_demo
from meemoo.api.deps import get_db
from meemoo.api.metrics_calc import (
    abandonment_composite,
    adherence_summary,
    engagement_series,
    human_contact_summary,
)
from meemoo.core.models import Alert, Conversation, Event, Usage
from meemoo.guardian.escalation import false_alarms_per_week

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["metrics"])

Db = Annotated[Session, Depends(get_db)]


@router.get("/metrics/engagement")
def get_engagement(
    db: Db, device_id: int = 1, days: int = 42, demo: bool = False
) -> dict[str, object]:
    """Engagement TRAJECTORY, not totals (Art. VIII §1): daily series with
    user-initiated share; week-6 marker is day index 42 on the client."""
    if demo:
        return metrics_demo.demo_engagement(days)
    series = engagement_series(db, device_id, days)
    return {
        "synthetic": False,
        "days": days,
        "series": [
            {**asdict(day), "user_share": round(day.user_share, 3)} for day in series
        ],
    }


@router.get("/metrics/adherence")
def get_adherence(
    db: Db, device_id: int = 1, days: int = 28, demo: bool = False
) -> dict[str, object]:
    if demo:
        return metrics_demo.demo_adherence()
    return {"synthetic": False, **adherence_summary(db, device_id, days)}


@router.get("/metrics/human-contact")
def get_human_contact(
    db: Db, device_id: int = 1, days: int = 28, demo: bool = False
) -> dict[str, object]:
    """The anti-substitution metric (Art. VIII §4)."""
    if demo:
        return metrics_demo.demo_human_contact()
    return {"synthetic": False, **human_contact_summary(db, device_id, days)}


class ContactBody(BaseModel):
    kind: str = Field(default="call", pattern="^(call|visit|video|message|other)$")
    note: str | None = Field(default=None, max_length=400)


@router.post("/devices/{device_id}/human-contact", status_code=201)
def log_human_contact(device_id: int, body: ContactBody, db: Db) -> dict[str, object]:
    """Log a real call/visit — the dashboard's 'we called Mom' button."""
    row = Event(
        device_id=device_id,
        type="human_contact.logged",
        payload={"kind": body.kind, "note": body.note or ""},
    )
    db.add(row)
    db.commit()
    logger.info(
        "human contact logged",
        extra={"fields": {"device_id": device_id, "kind": body.kind}},
    )
    return {"id": row.id, "kind": body.kind}


@router.get("/metrics/abandonment")
def get_abandonment(db: Db, device_id: int = 1, demo: bool = False) -> dict[str, object]:
    if demo:
        return metrics_demo.demo_abandonment()
    engagement = engagement_series(db, device_id, 28)
    adherence = adherence_summary(db, device_id, 28)
    return {"synthetic": False, **abandonment_composite(engagement, adherence)}


@router.get("/metrics/summary")
def get_summary(db: Db, device_id: int = 1, demo: bool = False) -> dict[str, object]:
    """The headline cards, false-alarms/week first (Art. VIII §3)."""
    if demo:
        return {
            "synthetic": True,
            "label": metrics_demo.SYNTHETIC_LABEL,
            "false_alarms": metrics_demo.demo_false_alarms(),
            "engagement": metrics_demo.demo_engagement(7),
            "human_contact": metrics_demo.demo_human_contact(),
            "abandonment": metrics_demo.demo_abandonment(),
        }
    engagement = engagement_series(db, device_id, 7)
    adherence = adherence_summary(db, device_id, 28)
    return {
        "synthetic": False,
        "false_alarms": {
            "false_alarms_last_7_days": false_alarms_per_week(db, device_id),
            "window_days": 7,
        },
        "engagement": {
            "sessions_7d": sum(d.sessions for d in engagement),
            "user_initiated_7d": sum(d.user_initiated for d in engagement),
        },
        "human_contact": human_contact_summary(db, device_id, 7),
        "abandonment": abandonment_composite(
            engagement_series(db, device_id, 28), adherence
        ),
    }


# ------------------------------------------------------------------- export
_EXPORT_COLUMNS: dict[str, tuple[type, list[str]]] = {
    "events": (Event, ["id", "device_id", "ts", "type", "payload"]),
    "conversations": (
        Conversation,
        ["id", "device_id", "person_id", "started_at", "ended_at", "mode", "trigger",
         "mood_note"],
    ),
    "alerts": (
        Alert,
        ["id", "device_id", "level", "state", "reason", "opened_at", "acknowledged_at"],
    ),
    "usage": (
        Usage,
        ["id", "device_id", "ts", "provider", "model", "tier", "input_tokens",
         "output_tokens", "cost_usd"],
    ),
}


@router.get("/export")
def export_csv(table: str, db: Db, device_id: int | None = None) -> Response:
    """One-command CSV export (research 07 §F.15). ``?table=events|…``."""
    spec = _EXPORT_COLUMNS.get(table)
    if spec is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown table; one of {sorted(_EXPORT_COLUMNS)}",
        )
    model, columns = spec
    query: Query[object] = db.query(model).order_by(
        model.id.asc()  # type: ignore[attr-defined]
    )
    if device_id is not None:
        query = query.filter(model.device_id == device_id)  # type: ignore[attr-defined]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in query.limit(100_000).all():
        writer.writerow([getattr(row, col) for col in columns])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=meemoo_{table}.csv"},
    )
