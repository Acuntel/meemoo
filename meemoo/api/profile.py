"""Device profile: the studio-saved configuration, resolved from the DB.

One place turns settings rows + the person row into the objects the runtime
needs (DeviceContext, ConversationBrain, voice character). Settings keys used
by the Studio (all optional — everything has a warm default, Art. IX §3):

- ``studio.custom_context``  {"text": str}           owner's raw instructions
- ``studio.reminders``       {"items": [{"time","label"}]}
- ``studio.interests``       {"items": [str]}
- ``preset.role``            {"role": str, "sub": str|null}
- ``voice.character``        {"key": "elder_male"|"child"|"female"}
- ``privacy.pause``          {"until": iso8601}       one-touch privacy pause
- ``privacy.permissions``    {recipient: {scope: bool}}  per-recipient matrix
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.engine import ConversationBrain
from meemoo.brain.personality import DeviceContext
from meemoo.core.models import Device, Person, Setting

logger = logging.getLogger(__name__)

DbFactory = sessionmaker[DbSession]


def get_setting(db: DbSession, device_id: int, key: str) -> dict[str, object] | None:
    """One settings value (JSON dict) or None."""
    row = (
        db.query(Setting)
        .filter(Setting.device_id == device_id, Setting.key == key)
        .one_or_none()
    )
    return dict(row.value) if row is not None else None


def set_setting(
    db: DbSession, device_id: int, key: str, value: dict[str, object]
) -> Setting:
    """Upsert one settings value. Caller commits."""
    row = (
        db.query(Setting)
        .filter(Setting.device_id == device_id, Setting.key == key)
        .one_or_none()
    )
    if row is None:
        row = Setting(device_id=device_id, key=key, value=value)
        db.add(row)
    else:
        row.value = value
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    return row


@dataclass(slots=True)
class DeviceProfile:
    """Everything the runtime needs to know about one device's config."""

    device_id: int = 1
    device_name: str = "Meemoo"
    mode: str = "home"
    store_transcripts: bool = True
    person_id: int | None = None
    person_name: str = "friend"
    room: str | None = None
    role: str = "companion"
    sub_preset: str | None = None
    voice: str = "elder_male"
    custom_context: str = ""
    reminders: list[str] = field(default_factory=list)
    privacy_paused_until: str | None = None


def _reminder_lines(raw: dict[str, object] | None) -> list[str]:
    items = raw.get("items") if raw else None
    if not isinstance(items, list):
        return []
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("label", "reminder"))
            when = str(item.get("time", ""))
            lines.append(f"{label} at {when}" if when else label)
    return lines


def load_profile_from(db: DbSession, device_id: int = 1) -> DeviceProfile:
    """Resolve the profile from an open session; misses fall back to defaults."""
    profile = DeviceProfile(device_id=device_id)
    device = db.get(Device, device_id)
    if device is not None:
        profile.device_name = device.name
        profile.mode = device.mode
        profile.store_transcripts = bool(device.store_transcripts)
    person = (
        db.query(Person)
        .filter(Person.device_id == device_id)
        .order_by(Person.id.asc())
        .first()
    )
    if person is not None:
        profile.person_id = person.id
        profile.person_name = person.preferred_name or person.name
        profile.room = person.room
    preset = get_setting(db, device_id, "preset.role")
    if preset is not None:
        profile.role = str(preset.get("role", profile.role))
        sub = preset.get("sub")
        profile.sub_preset = str(sub) if sub else None
    voice = get_setting(db, device_id, "voice.character")
    if voice is not None:
        profile.voice = str(voice.get("key", profile.voice))
    custom = get_setting(db, device_id, "studio.custom_context")
    if custom is not None:
        profile.custom_context = str(custom.get("text", ""))
    profile.reminders = _reminder_lines(get_setting(db, device_id, "studio.reminders"))
    pause = get_setting(db, device_id, "privacy.pause")
    if pause is not None:
        until = str(pause.get("until", ""))
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        profile.privacy_paused_until = until if until > now else None
    return profile


def load_profile(db_factory: DbFactory | None, device_id: int = 1) -> DeviceProfile:
    """Resolve the profile from the DB; every miss falls back to a default."""
    if db_factory is None:
        return DeviceProfile(device_id=device_id)
    with db_factory() as db:
        return load_profile_from(db, device_id)


def db_factory_or_none() -> DbFactory | None:
    """The process DB factory, or None when the schema isn't there (Art. IX §3)."""
    from meemoo.core.db import get_session_factory

    try:
        factory = get_session_factory()
        with factory() as db:
            db.query(Device.id).first()
        return factory
    except Exception:
        logger.warning("process DB unavailable — degrading to memory-only")
        return None


def build_brain(db_factory: DbFactory | None, device_id: int = 1) -> ConversationBrain:
    """A ConversationBrain wired from the device's saved profile."""
    profile = load_profile(db_factory, device_id)
    return ConversationBrain(
        device_id=device_id,
        db_factory=db_factory,
        device=DeviceContext(
            person_name=profile.person_name,
            mode=profile.mode,
            room=profile.room,
            reminders=list(profile.reminders),
        ),
        person_id=profile.person_id,
        role=profile.role,
        sub_preset=profile.sub_preset,
        custom_context=profile.custom_context,
    )
