"""Setup Studio REST: extract → review/edit → apply (MASTER_PROMPT §6).

The owner types plain language; ``/studio/extract`` returns the structured
config for review; ``/studio/apply`` saves it — person row, reminders,
custom context (always stored verbatim), preset role, voice. "Prompting your
robot" as a first-class product experience.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from meemoo.api.deps import get_db
from meemoo.api.profile import (
    db_factory_or_none,
    get_setting,
    load_profile_from,
    set_setting,
)
from meemoo.api.studio_extract import StudioConfig, extract
from meemoo.core.models import Person, append_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])

Db = Annotated[Session, Depends(get_db)]


class ExtractBody(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    device_id: int = 1


class ExtractOut(BaseModel):
    config: StudioConfig
    source: str  # "model" | "deterministic"
    raw_text: str


@router.post("/extract")
def studio_extract(body: ExtractBody) -> ExtractOut:
    """Plain language → structured config for review (never crashes keyless)."""
    config, source = extract(body.text, db_factory_or_none(), body.device_id)
    logger.info(
        "studio extraction",
        extra={"fields": {"source": source, "chars": len(body.text)}},
    )
    return ExtractOut(config=config, source=source, raw_text=body.text)


class ApplyBody(BaseModel):
    device_id: int = 1
    config: StudioConfig
    raw_text: str = ""
    role: str | None = None
    sub_preset: str | None = None
    voice: str | None = None


@router.post("/apply")
def studio_apply(body: ApplyBody, db: Db) -> dict[str, object]:
    """Persist the reviewed config; raw instructions become custom context."""
    config = body.config
    person = (
        db.query(Person)
        .filter(Person.device_id == body.device_id)
        .order_by(Person.id.asc())
        .first()
    )
    if person is None:
        person = Person(device_id=body.device_id, name=config.person_name)
        db.add(person)
        db.flush()
    else:
        person.name = config.person_name
    if config.relationship:
        person.notes = f"relationship: {config.relationship}"

    if body.raw_text.strip():
        set_setting(db, body.device_id, "studio.custom_context", {"text": body.raw_text})
    set_setting(db, body.device_id, "studio.reminders", {
        "items": [r.model_dump() for r in config.reminders],
    })
    set_setting(db, body.device_id, "studio.interests", {"items": list(config.interests)})
    set_setting(db, body.device_id, "studio.tone", {"items": list(config.tone)})
    if config.escalation_note:
        set_setting(
            db, body.device_id, "studio.escalation_note", {"text": config.escalation_note}
        )
    if body.role:
        set_setting(
            db, body.device_id, "preset.role", {"role": body.role, "sub": body.sub_preset}
        )
    if body.voice:
        set_setting(db, body.device_id, "voice.character", {"key": body.voice})

    append_audit(  # config changes are flight-recorder events (Art. II §6)
        db,
        device_id=body.device_id,
        actor="studio",
        action="studio.config_applied",
        detail=f"person={config.person_name} reminders={len(config.reminders)}",
    )
    db.commit()
    logger.info(
        "studio config applied",
        extra={"fields": {"device_id": body.device_id,
                          "person": config.person_name,
                          "reminders": len(config.reminders)}},
    )
    return {"saved": True, "person_id": person.id}


@router.get("/current")
def studio_current(db: Db, device_id: int = 1) -> dict[str, object]:
    """The saved config, for Studio prefill."""
    profile = load_profile_from(db, device_id)
    custom = get_setting(db, device_id, "studio.custom_context") or {}
    reminders = get_setting(db, device_id, "studio.reminders") or {}
    interests = get_setting(db, device_id, "studio.interests") or {}
    tone = get_setting(db, device_id, "studio.tone") or {}
    return {
        "device_id": device_id,
        "person_name": profile.person_name,
        "person_id": profile.person_id,
        "role": profile.role,
        "sub_preset": profile.sub_preset,
        "voice": profile.voice,
        "custom_context": custom.get("text", ""),
        "reminders": reminders.get("items", []),
        "interests": interests.get("items", []),
        "tone": tone.get("items", []),
        "privacy_paused_until": profile.privacy_paused_until,
        "store_transcripts": profile.store_transcripts,
    }
