"""Device-scoped media store + the A3 auto-purge rule.

Room photos are context for Meemoo's map, not surveillance: they live under
``<media_dir>/device_<id>/rooms/<room>/`` on the base station, are listed and
deletable in Studio, and never leave the machine.

Auto-purge (Amendment A3): any room photo or event thumbnail whose location
tag falls inside an off-limit zone is deleted immediately, each deletion
recorded as an append-only audit row. Event rows themselves are append-only
(the flight recorder is never rewritten) — for those the FILE is removed and
the audit row records why the evidence is gone.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from meemoo.core.models import Event, RoomCapture, append_audit
from meemoo.flight.zones import Zone, zone_containing

logger = logging.getLogger(__name__)

_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def room_slug(room: str) -> str:
    """Filesystem-safe room directory name."""
    slug = re.sub(r"[^a-z0-9]+", "-", room.lower()).strip("-")
    return slug or "room"


def rooms_dir(media_root: Path, device_id: int) -> Path:
    return media_root / f"device_{device_id}" / "rooms"


def save_room_photo(
    media_root: Path,
    device_id: int,
    room: str,
    image_base64: str,
    content_type: str,
) -> Path | None:
    """Decode and store one captured photo; None if the data is not decodable."""
    extension = _EXTENSIONS.get(content_type)
    if extension is None:
        return None
    try:
        data = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not data:
        return None
    target_dir = rooms_dir(media_root, device_id) / room_slug(room)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{uuid.uuid4().hex}{extension}"
    path.write_bytes(data)
    return path


def delete_media_file(path_str: str) -> None:
    """Remove a stored file; missing files are already gone (never raises)."""
    try:
        Path(path_str).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("media delete failed for %s: %s", path_str, exc)


def _event_location(payload: dict[str, object]) -> tuple[float, float] | None:
    x, y = payload.get("x"), payload.get("y")
    if isinstance(x, int | float) and isinstance(y, int | float):
        return float(x), float(y)
    return None


def purge_zone_media(db: Session, device_id: int, zones: list[Zone]) -> int:
    """Delete every media item whose location tag falls in a zone (A3).

    Returns the number of items purged. Caller commits. Room-photo rows are
    deleted outright; event rows are append-only, so their thumbnail FILE is
    removed and the row's path now points at nothing — the audit row is the
    record of why.
    """
    if not zones:
        return 0
    purged = 0
    captures = db.query(RoomCapture).filter(RoomCapture.device_id == device_id).all()
    for capture in captures:
        if capture.x is None or capture.y is None:
            continue
        zone = zone_containing(zones, capture.x, capture.y)
        if zone is None:
            continue
        delete_media_file(capture.path)
        db.delete(capture)
        append_audit(
            db,
            device_id=device_id,
            actor="media_purge",
            action="media.auto_purged",
            trigger=f"off-limit zone: {zone.name}",
            detail=f"room photo of {capture.room} deleted (Amendment A3)",
        )
        purged += 1
    events = (
        db.query(Event)
        .filter(Event.device_id == device_id, Event.thumbnail_path.is_not(None))
        .all()
    )
    for row in events:
        location = _event_location(dict(row.payload))
        if location is None or row.thumbnail_path is None:
            continue
        zone = zone_containing(zones, *location)
        if zone is None or not Path(row.thumbnail_path).exists():
            continue
        delete_media_file(row.thumbnail_path)
        append_audit(
            db,
            device_id=device_id,
            actor="media_purge",
            action="media.auto_purged",
            trigger=f"off-limit zone: {zone.name}",
            evidence_event_id=row.id,
            detail=f"event thumbnail for {row.type} deleted (Amendment A3)",
        )
        purged += 1
    if purged:
        logger.info(
            "auto-purge removed media in off-limit zones",
            extra={"fields": {"device_id": device_id, "purged": purged}},
        )
    return purged
