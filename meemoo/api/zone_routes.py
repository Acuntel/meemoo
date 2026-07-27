"""Off-limit zones REST + goto (Amendments A3/A5/A6).

Zones are hard boundaries: creating one immediately pushes it into the
running sim (routes and goto refuse it) and sweeps existing media whose
location tag falls inside (auto-purge, each deletion audited). ``goto`` is
how a named pin becomes a destination; a goto into a zone answers with a
refusal instead of a flight.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from meemoo.api.deps import get_db
from meemoo.api.media import purge_zone_media
from meemoo.core.models import NoGoZoneRow, append_audit
from meemoo.flight.registry import get_active_sim
from meemoo.flight.zones import Zone, zone_containing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["zones"])

Db = Annotated[Session, Depends(get_db)]


class ZoneBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)
    reason: str = Field(default="user", pattern="^(user|bathroom)$")


class ZoneOut(ZoneBody):
    id: int
    device_id: int


def _zone_out(row: NoGoZoneRow) -> ZoneOut:
    return ZoneOut.model_validate(row, from_attributes=True)


def _db_zones(db: Session, device_id: int) -> list[Zone]:
    rows = db.query(NoGoZoneRow).filter(NoGoZoneRow.device_id == device_id).all()
    return [Zone(z.name, z.x, z.y, z.w, z.h) for z in rows]


def _sync_sim(db: Session, device_id: int) -> None:
    """Push the DB zone list into the running sim (no-op in API-only mode)."""
    sim = get_active_sim()
    if sim is not None and sim.device_id == device_id:
        sim.set_no_go_zones(_db_zones(db, device_id))


@router.get("/devices/{device_id}/zones")
def list_zones(device_id: int, db: Db) -> list[ZoneOut]:
    rows = (
        db.query(NoGoZoneRow)
        .filter(NoGoZoneRow.device_id == device_id)
        .order_by(NoGoZoneRow.id.asc())
        .all()
    )
    return [_zone_out(r) for r in rows]


@router.post("/devices/{device_id}/zones", status_code=201)
def create_zone(device_id: int, body: ZoneBody, db: Db) -> dict[str, object]:
    row = NoGoZoneRow(device_id=device_id, **body.model_dump())
    db.add(row)
    append_audit(
        db,
        device_id=device_id,
        actor="onboarding",
        action="zone.created",
        detail=f"{body.name} marked off limits ({body.reason})",
    )
    db.flush()
    purged = purge_zone_media(db, device_id, [Zone(row.name, row.x, row.y, row.w, row.h)])
    db.commit()
    _sync_sim(db, device_id)
    logger.info(
        "off-limit zone created",
        extra={"fields": {"device_id": device_id, "name": body.name, "purged": purged}},
    )
    return {**_zone_out(row).model_dump(), "purged": purged}


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: int, db: Db) -> None:
    row = db.get(NoGoZoneRow, zone_id)
    if row is None:
        raise HTTPException(status_code=404, detail="zone not found")
    device_id = row.device_id
    append_audit(
        db,
        device_id=device_id,
        actor="onboarding",
        action="zone.deleted",
        detail=f"{row.name} is no longer off limits",
    )
    db.delete(row)
    db.commit()
    _sync_sim(db, device_id)


# --------------------------------------------------------------------- goto
class GotoBody(BaseModel):
    x: float
    y: float
    label: str | None = Field(default=None, max_length=120)


@router.post("/devices/{device_id}/goto")
async def goto(device_id: int, body: GotoBody, db: Db) -> dict[str, object]:
    """Send Meemoo to a point or named pin; zones answer with a refusal."""
    zones = _db_zones(db, device_id)
    sim = get_active_sim()
    if sim is None:
        zone = zone_containing(zones, body.x, body.y)
        if zone is not None:
            return {
                "started": False,
                "refused": True,
                "reason": f"{zone.name} is off limits, so Meemoo stays out",
            }
        return {"started": False, "refused": False, "reason": "Meemoo isn't flying right now"}
    if sim.device_id == device_id:
        sim.set_no_go_zones(zones)
    started = sim.goto(body.x, body.y, label=body.label)
    if not started:
        zone = zone_containing(zones, body.x, body.y)
        zone_name = zone.name if zone is not None else "that area"
        return {
            "started": False,
            "refused": True,
            "reason": f"{zone_name} is off limits, so Meemoo stays out",
        }
    return {"started": True, "refused": False, "reason": None}
