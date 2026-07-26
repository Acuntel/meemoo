"""Fleet REST: devices, persons, consent records, per-device settings.

Every table is keyed by device_id (Art. VII §2 fleet-ready). The settings
endpoints are the generic JSON key/value store the Studio's privacy panel
uses (permission matrix, privacy pause, custom context — see api/profile.py
for the key vocabulary).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from meemoo.api.deps import get_db
from meemoo.api.profile import get_setting, set_setting
from meemoo.core.models import ConsentRecord, Device, Person, Setting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["fleet"])

Db = Annotated[Session, Depends(get_db)]


# ------------------------------------------------------------------- devices
class DeviceBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    mode: str = Field(default="home", pattern="^(home|facility)$")
    store_transcripts: bool = True
    is_active: bool = True


class DevicePatch(BaseModel):
    name: str | None = None
    mode: str | None = Field(default=None, pattern="^(home|facility)$")
    store_transcripts: bool | None = None
    is_active: bool | None = None


class DeviceOut(DeviceBody):
    id: int


def _device_out(row: Device) -> DeviceOut:
    return DeviceOut.model_validate(row, from_attributes=True)


@router.get("/devices")
def list_devices(db: Db) -> list[DeviceOut]:
    return [_device_out(d) for d in db.query(Device).order_by(Device.id.asc()).all()]


@router.post("/devices", status_code=201)
def create_device(body: DeviceBody, db: Db) -> DeviceOut:
    row = Device(**body.model_dump())
    db.add(row)
    db.commit()
    return _device_out(row)


@router.get("/devices/{device_id}")
def get_device(device_id: int, db: Db) -> DeviceOut:
    row = db.get(Device, device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="device not found")
    return _device_out(row)


@router.patch("/devices/{device_id}")
def patch_device(device_id: int, body: DevicePatch, db: Db) -> DeviceOut:
    row = db.get(Device, device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="device not found")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(row, key, value)
    db.commit()
    logger.info("device updated", extra={"fields": {"device_id": device_id}})
    return _device_out(row)


# ------------------------------------------------------------------- persons
class PersonBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    preferred_name: str | None = None
    room: str | None = None
    notes: str | None = None


class PersonOut(PersonBody):
    id: int
    device_id: int


def _person_out(row: Person) -> PersonOut:
    return PersonOut.model_validate(row, from_attributes=True)


@router.get("/devices/{device_id}/persons")
def list_persons(device_id: int, db: Db) -> list[PersonOut]:
    rows = db.query(Person).filter(Person.device_id == device_id).order_by(Person.id.asc())
    return [_person_out(p) for p in rows.all()]


@router.post("/devices/{device_id}/persons", status_code=201)
def create_person(device_id: int, body: PersonBody, db: Db) -> PersonOut:
    row = Person(device_id=device_id, **body.model_dump())
    db.add(row)
    db.commit()
    return _person_out(row)


@router.put("/persons/{person_id}")
def update_person(person_id: int, body: PersonBody, db: Db) -> PersonOut:
    row = db.get(Person, person_id)
    if row is None:
        raise HTTPException(status_code=404, detail="person not found")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return _person_out(row)


@router.delete("/persons/{person_id}", status_code=204)
def delete_person(person_id: int, db: Db) -> None:
    row = db.get(Person, person_id)
    if row is None:
        raise HTTPException(status_code=404, detail="person not found")
    db.delete(row)
    db.commit()


# ------------------------------------------------------------------- consent
class ConsentBody(BaseModel):
    person_id: int
    scope: str = Field(min_length=1, max_length=120)
    method: str = Field(default="app", max_length=40)
    consenting_party: str = Field(min_length=1, max_length=120)
    is_surrogate: bool = False
    surrogate_relationship: str | None = None
    granted: bool = True


class ConsentOut(ConsentBody):
    id: int
    device_id: int
    revoked_at: str | None = None


def _consent_out(row: ConsentRecord) -> ConsentOut:
    return ConsentOut(
        id=row.id,
        device_id=row.device_id,
        person_id=row.person_id,
        scope=row.scope,
        method=row.method,
        consenting_party=row.consenting_party,
        is_surrogate=row.is_surrogate,
        surrogate_relationship=row.surrogate_relationship,
        granted=row.granted,
        revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
    )


@router.get("/devices/{device_id}/consent")
def list_consent(device_id: int, db: Db) -> list[ConsentOut]:
    rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.device_id == device_id)
        .order_by(ConsentRecord.id.desc())
        .all()
    )
    return [_consent_out(r) for r in rows]


@router.post("/devices/{device_id}/consent", status_code=201)
def create_consent(device_id: int, body: ConsentBody, db: Db) -> ConsentOut:
    row = ConsentRecord(device_id=device_id, **body.model_dump())
    db.add(row)
    db.commit()
    return _consent_out(row)


@router.post("/consent/{consent_id}/revoke")
def revoke_consent(consent_id: int, db: Db) -> ConsentOut:
    row = db.get(ConsentRecord, consent_id)
    if row is None:
        raise HTTPException(status_code=404, detail="consent record not found")
    row.granted = False
    row.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    logger.info("consent revoked", extra={"fields": {"consent_id": consent_id}})
    return _consent_out(row)


# ------------------------------------------------------------------ settings
class SettingBody(BaseModel):
    value: dict[str, object]


@router.get("/devices/{device_id}/settings")
def list_settings(device_id: int, db: Db) -> dict[str, dict[str, object]]:
    rows = db.query(Setting).filter(Setting.device_id == device_id).all()
    return {row.key: dict(row.value) for row in rows}


@router.get("/devices/{device_id}/settings/{key}")
def get_one_setting(device_id: int, key: str, db: Db) -> dict[str, object]:
    value = get_setting(db, device_id, key)
    if value is None:
        raise HTTPException(status_code=404, detail="setting not found")
    return value


@router.put("/devices/{device_id}/settings/{key}")
def put_setting(device_id: int, key: str, body: SettingBody, db: Db) -> dict[str, object]:
    row = set_setting(db, device_id, key, body.value)
    db.commit()
    return dict(row.value)


# ------------------------------------------------------------- privacy pause
class PauseBody(BaseModel):
    minutes: int = Field(default=15, ge=1, le=480)


@router.post("/devices/{device_id}/privacy/pause")
def privacy_pause(device_id: int, body: PauseBody, db: Db) -> dict[str, object]:
    """One-touch privacy pause (Art. V §4): perception+voice sit out."""
    until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=body.minutes)
    set_setting(db, device_id, "privacy.pause", {"until": until.isoformat()})
    db.commit()
    logger.info(
        "privacy pause set",
        extra={"fields": {"device_id": device_id, "minutes": body.minutes}},
    )
    return {"paused_until": until.isoformat()}


@router.delete("/devices/{device_id}/privacy/pause")
def privacy_resume(device_id: int, db: Db) -> dict[str, object]:
    set_setting(db, device_id, "privacy.pause", {"until": ""})
    db.commit()
    return {"paused_until": None}
