"""Onboarding REST (Amendments A1/A6): setup record, pairing, room photos.

The wizard walks: what kind of place -> room capture -> pin drop -> off-limit
zones -> pairing code -> plan. This module owns the record + pairing + photo
endpoints; zones live in zone_routes.py. Photos are stored on the base
station only and stay viewable/deletable in Studio.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from meemoo.api.deps import get_db
from meemoo.api.media import delete_media_file as _delete_file
from meemoo.api.media import save_room_photo
from meemoo.core.config import get_settings
from meemoo.core.models import (
    ROOM_PHOTO_TARGET,
    Device,
    NoGoZoneRow,
    OnboardingRecord,
    RoomCapture,
    append_audit,
)
from meemoo.flight.floorplan import load_plan
from meemoo.flight.registry import get_active_sim
from meemoo.flight.zones import Zone, zone_containing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["onboarding"])

Db = Annotated[Session, Depends(get_db)]

DWELLING_TYPES = ("house", "apartment", "senior_room", "hospital_room")
STEPS = ("place", "rooms", "pins", "zones", "pairing", "plan")
PAIRING_CODE_RE = re.compile(r"^MEEMOO-[A-Z0-9]{4}-[A-Z0-9]{4}$")


# ------------------------------------------------------------------- record
class OnboardingOut(BaseModel):
    exists: bool
    completed: bool
    dwelling_type: str | None = None
    step: str = "place"
    paired: bool = False


class OnboardingPatch(BaseModel):
    dwelling_type: str | None = None
    step: str | None = None


def _record_out(row: OnboardingRecord | None, device: Device | None) -> OnboardingOut:
    paired = device is not None and device.pairing_code is not None
    if row is None:
        return OnboardingOut(exists=False, completed=False, paired=paired)
    return OnboardingOut(
        exists=True,
        completed=row.completed_at is not None,
        dwelling_type=row.dwelling_type,
        step=row.step,
        paired=paired,
    )


@router.get("/devices/{device_id}/onboarding")
def get_onboarding(device_id: int, db: Db) -> OnboardingOut:
    row = (
        db.query(OnboardingRecord)
        .filter(OnboardingRecord.device_id == device_id)
        .one_or_none()
    )
    return _record_out(row, db.get(Device, device_id))


@router.put("/devices/{device_id}/onboarding")
def put_onboarding(device_id: int, body: OnboardingPatch, db: Db) -> OnboardingOut:
    if body.dwelling_type is not None and body.dwelling_type not in DWELLING_TYPES:
        raise HTTPException(
            status_code=400, detail=f"dwelling_type must be one of {DWELLING_TYPES}"
        )
    if body.step is not None and body.step not in STEPS:
        raise HTTPException(status_code=400, detail=f"step must be one of {STEPS}")
    row = (
        db.query(OnboardingRecord)
        .filter(OnboardingRecord.device_id == device_id)
        .one_or_none()
    )
    if row is None:
        row = OnboardingRecord(device_id=device_id)
        db.add(row)
    if body.dwelling_type is not None:
        row.dwelling_type = body.dwelling_type
    if body.step is not None:
        row.step = body.step
    db.commit()
    return _record_out(row, db.get(Device, device_id))


@router.post("/devices/{device_id}/onboarding/complete")
def complete_onboarding(device_id: int, db: Db) -> OnboardingOut:
    row = (
        db.query(OnboardingRecord)
        .filter(OnboardingRecord.device_id == device_id)
        .one_or_none()
    )
    if row is None:
        row = OnboardingRecord(device_id=device_id)
        db.add(row)
    row.completed_at = datetime.now(UTC).replace(tzinfo=None)
    append_audit(db, device_id=device_id, actor="onboarding", action="onboarding.completed")
    db.commit()
    logger.info("onboarding completed", extra={"fields": {"device_id": device_id}})
    return _record_out(row, db.get(Device, device_id))


# ------------------------------------------------------------------ pairing
class PairBody(BaseModel):
    code: str = Field(min_length=1, max_length=40)


@router.post("/devices/{device_id}/pair")
def pair_device(device_id: int, body: PairBody, db: Db) -> dict[str, object]:
    """Bind the code printed on the aircraft to this base station (A1)."""
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    code = body.code.strip().upper()
    if not PAIRING_CODE_RE.fullmatch(code):
        raise HTTPException(
            status_code=400,
            detail="That code doesn't look right. It's printed as MEEMOO-XXXX-XXXX.",
        )
    device.pairing_code = code
    append_audit(
        db, device_id=device_id, actor="onboarding", action="device.paired", detail=code
    )
    db.commit()
    logger.info("aircraft paired", extra={"fields": {"device_id": device_id}})
    return {"paired": True, "code": code}


# ------------------------------------------------------------- room capture
def _room_center(room: str) -> tuple[float, float] | None:
    """Center of the named floor-plan room (the photo's location tag)."""
    sim = get_active_sim()
    try:
        plan = sim.plan if sim is not None else load_plan(get_settings().meemoo_plan)
    except ValueError:
        return None
    for r in plan.rooms:
        if r.name.lower() == room.lower():
            return (r.x + r.w / 2.0, r.y + r.h / 2.0)
    return None


def _zones(db: Session, device_id: int) -> list[Zone]:
    rows = db.query(NoGoZoneRow).filter(NoGoZoneRow.device_id == device_id).all()
    return [Zone(z.name, z.x, z.y, z.w, z.h) for z in rows]


class PhotoBody(BaseModel):
    image_base64: str = Field(min_length=1)
    content_type: str = Field(default="image/jpeg", max_length=40)


class PhotoOut(BaseModel):
    id: int
    room: str
    created_at: str


class RoomSummary(BaseModel):
    room: str
    photo_count: int
    target: int = ROOM_PHOTO_TARGET
    last_captured_at: str | None = None


@router.get("/devices/{device_id}/rooms")
def list_rooms(device_id: int, db: Db) -> list[RoomSummary]:
    rows = (
        db.query(RoomCapture)
        .filter(RoomCapture.device_id == device_id)
        .order_by(RoomCapture.id.asc())
        .all()
    )
    summary: dict[str, RoomSummary] = {}
    for row in rows:
        entry = summary.setdefault(row.room, RoomSummary(room=row.room, photo_count=0))
        entry.photo_count += 1
        entry.last_captured_at = row.created_at.isoformat()
    return list(summary.values())


@router.post("/devices/{device_id}/rooms/{room}/photos", status_code=201)
def upload_photo(device_id: int, room: str, body: PhotoBody, db: Db) -> PhotoOut:
    center = _room_center(room)
    if center is not None:
        zone = zone_containing(_zones(db, device_id), *center)
        if zone is not None:
            raise HTTPException(
                status_code=403,
                detail=f"{zone.name} is off limits, so Meemoo doesn't keep photos of it.",
            )
    media_root = Path(get_settings().meemoo_media_dir)
    path = save_room_photo(media_root, device_id, room, body.image_base64, body.content_type)
    if path is None:
        raise HTTPException(status_code=400, detail="That image couldn't be read.")
    row = RoomCapture(
        device_id=device_id,
        room=room,
        path=str(path),
        x=center[0] if center else None,
        y=center[1] if center else None,
    )
    db.add(row)
    db.commit()
    return PhotoOut(id=row.id, room=row.room, created_at=row.created_at.isoformat())


@router.get("/devices/{device_id}/rooms/{room}/photos")
def list_photos(device_id: int, room: str, db: Db) -> list[PhotoOut]:
    rows = (
        db.query(RoomCapture)
        .filter(RoomCapture.device_id == device_id, RoomCapture.room == room)
        .order_by(RoomCapture.id.asc())
        .all()
    )
    return [PhotoOut(id=r.id, room=r.room, created_at=r.created_at.isoformat()) for r in rows]


@router.get("/photos/{photo_id}")
def get_photo(photo_id: int, db: Db) -> FileResponse:
    row = db.get(RoomCapture, photo_id)
    if row is None or not Path(row.path).exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(row.path)


@router.delete("/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int, db: Db) -> None:
    row = db.get(RoomCapture, photo_id)
    if row is None:
        raise HTTPException(status_code=404, detail="photo not found")
    _delete_file(row.path)
    db.delete(row)
    db.commit()


@router.delete("/devices/{device_id}/rooms/{room}/photos")
def retake_room(device_id: int, room: str, db: Db) -> dict[str, object]:
    """Furniture moved? Clear the room so it can be captured fresh."""
    rows = (
        db.query(RoomCapture)
        .filter(RoomCapture.device_id == device_id, RoomCapture.room == room)
        .all()
    )
    for row in rows:
        _delete_file(row.path)
        db.delete(row)
    db.commit()
    return {"deleted": len(rows), "room": room}
