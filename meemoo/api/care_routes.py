"""Care REST: check-in schedule, conversations, events, routes, run-round.

``POST /devices/{id}/rounds/run`` is demo-script step 3's button: it fires a
``checkin.due`` on the live bus (guardian speaks + dispatches the sim). With
no runtime it answers honestly instead of pretending (Art. IX §3).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from datetime import time as dtime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from meemoo.api.deps import get_db
from meemoo.core import topics
from meemoo.core.bus_registry import get_active_bus
from meemoo.core.models import (
    CheckinSchedule,
    Conversation,
    Event,
    Message,
    Route,
    Waypoint,
)
from meemoo.guardian.scheduler import DEFAULT_CHECKIN_TIMES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["care"])

Db = Annotated[Session, Depends(get_db)]


# ------------------------------------------------------------------ schedule
class ScheduleBody(BaseModel):
    time_of_day: str = Field(pattern=r"^([01]?\d|2[0-3]):[0-5]\d$")
    label: str | None = None
    enabled: bool = True


class ScheduleOut(ScheduleBody):
    id: int
    device_id: int


@router.get("/devices/{device_id}/schedule")
def list_schedule(device_id: int, db: Db) -> list[ScheduleOut]:
    rows = (
        db.query(CheckinSchedule)
        .filter(CheckinSchedule.device_id == device_id)
        .order_by(CheckinSchedule.time_of_day.asc())
        .all()
    )
    return [ScheduleOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/devices/{device_id}/schedule", status_code=201)
def create_schedule(device_id: int, body: ScheduleBody, db: Db) -> ScheduleOut:
    row = CheckinSchedule(device_id=device_id, **body.model_dump())
    db.add(row)
    db.commit()
    return ScheduleOut.model_validate(row, from_attributes=True)


@router.put("/schedule/{schedule_id}")
def update_schedule(schedule_id: int, body: ScheduleBody, db: Db) -> ScheduleOut:
    row = db.get(CheckinSchedule, schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="schedule entry not found")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return ScheduleOut.model_validate(row, from_attributes=True)


@router.delete("/schedule/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Db) -> None:
    row = db.get(CheckinSchedule, schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="schedule entry not found")
    db.delete(row)
    db.commit()


@router.get("/devices/{device_id}/next-checkin")
def next_checkin(device_id: int, db: Db) -> dict[str, object]:
    """The next scheduled check-in time (device rows or the defaults)."""
    rows = (
        db.query(CheckinSchedule)
        .filter(CheckinSchedule.device_id == device_id, CheckinSchedule.enabled.is_(True))
        .order_by(CheckinSchedule.time_of_day.asc())
        .all()
    )
    times = [r.time_of_day for r in rows] or list(DEFAULT_CHECKIN_TIMES)
    now = datetime.now()
    today = now.strftime("%H:%M")
    upcoming = next((t for t in times if t > today), None)
    if upcoming is None:  # tomorrow's first
        upcoming = times[0]
        when = datetime.combine(now.date() + timedelta(days=1), _as_time(upcoming))
    else:
        when = datetime.combine(now.date(), _as_time(upcoming))
    return {"time": upcoming, "at": when.isoformat(), "times": times}


def _as_time(hhmm: str) -> dtime:
    hour, _, minute = hhmm.partition(":")
    return dtime(hour=int(hour), minute=int(minute or 0))


# ---------------------------------------------------------------- run a round
@router.post("/devices/{device_id}/rounds/run")
async def run_round(device_id: int) -> dict[str, object]:
    """Fire a check-in now: guardian speaks, sim flies (demo step 3)."""
    bus = get_active_bus()
    if bus is None:
        return {"started": False, "reason": "runtime not running (API-only mode)"}
    await bus.publish(
        topics.CHECKIN_DUE, {"device_id": device_id, "time": "manual", "label": "manual"}
    )
    logger.info("manual round fired", extra={"fields": {"device_id": device_id}})
    return {"started": True}


# ------------------------------------------------------------- conversations
class ConversationOut(BaseModel):
    id: int
    device_id: int
    person_id: int | None
    started_at: str
    ended_at: str | None
    mode: str
    trigger: str
    mood_note: str | None
    message_count: int


@router.get("/conversations")
def list_conversations(
    db: Db, device_id: int | None = None, limit: int = 50
) -> list[ConversationOut]:
    query = db.query(Conversation).order_by(Conversation.id.desc())
    if device_id is not None:
        query = query.filter(Conversation.device_id == device_id)
    out: list[ConversationOut] = []
    for row in query.limit(min(limit, 200)).all():
        count = db.query(Message).filter(Message.conversation_id == row.id).count()
        out.append(ConversationOut(
            id=row.id, device_id=row.device_id, person_id=row.person_id,
            started_at=row.started_at.isoformat(),
            ended_at=row.ended_at.isoformat() if row.ended_at else None,
            mode=row.mode, trigger=row.trigger, mood_note=row.mood_note,
            message_count=count,
        ))
    return out


class MessageOut(BaseModel):
    id: int
    ts: str
    role: str
    content: str


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, db: Db) -> list[MessageOut]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .all()
    )
    return [
        MessageOut(id=m.id, ts=m.ts.isoformat(), role=m.role, content=m.content)
        for m in rows
    ]


# -------------------------------------------------------------------- events
class EventOut(BaseModel):
    id: int
    device_id: int
    ts: str
    type: str
    payload: dict[str, object]
    thumbnail_path: str | None


@router.get("/events")
def list_events(
    db: Db,
    device_id: int | None = None,
    type_prefix: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[EventOut]:
    query = db.query(Event).order_by(Event.id.desc())
    if device_id is not None:
        query = query.filter(Event.device_id == device_id)
    if type_prefix:
        query = query.filter(Event.type.like(f"{type_prefix}%"))
    if since:
        query = query.filter(Event.ts >= datetime.fromisoformat(since))
    return [
        EventOut(
            id=e.id, device_id=e.device_id, ts=e.ts.isoformat(), type=e.type,
            payload=dict(e.payload), thumbnail_path=e.thumbnail_path,
        )
        for e in query.limit(min(limit, 500)).all()
    ]


# -------------------------------------------------------------------- routes
class WaypointBody(BaseModel):
    order_index: int = 0
    kind: str = Field(default="area", pattern="^(area|person|door)$")
    label: str | None = None
    x: float
    y: float
    person_id: int | None = None


class RouteBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_default: bool = False
    waypoints: list[WaypointBody] = Field(default_factory=list)


class RouteOut(BaseModel):
    id: int
    device_id: int
    name: str
    is_default: bool
    waypoints: list[WaypointBody]


def _route_out(db: Session, row: Route) -> RouteOut:
    wps = (
        db.query(Waypoint)
        .filter(Waypoint.route_id == row.id)
        .order_by(Waypoint.order_index.asc())
        .all()
    )
    return RouteOut(
        id=row.id, device_id=row.device_id, name=row.name, is_default=row.is_default,
        waypoints=[WaypointBody.model_validate(w, from_attributes=True) for w in wps],
    )


@router.get("/devices/{device_id}/routes")
def list_routes(device_id: int, db: Db) -> list[RouteOut]:
    rows = db.query(Route).filter(Route.device_id == device_id).order_by(Route.id.asc())
    return [_route_out(db, r) for r in rows.all()]


@router.post("/devices/{device_id}/routes", status_code=201)
def create_route(device_id: int, body: RouteBody, db: Db) -> RouteOut:
    row = Route(device_id=device_id, name=body.name, is_default=body.is_default)
    db.add(row)
    db.flush()
    for wp in body.waypoints:
        db.add(Waypoint(route_id=row.id, **wp.model_dump()))
    db.commit()
    return _route_out(db, row)


@router.delete("/routes/{route_id}", status_code=204)
def delete_route(route_id: int, db: Db) -> None:
    row = db.get(Route, route_id)
    if row is None:
        raise HTTPException(status_code=404, detail="route not found")
    db.query(Waypoint).filter(Waypoint.route_id == route_id).delete()
    db.delete(row)
    db.commit()
