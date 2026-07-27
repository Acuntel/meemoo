"""Onboarding tables: setup progress, room capture photos, off-limit zones.

Amendment A6: onboarding asks what kind of place this is, captures each
covered room (~20 detailed photos, re-capturable when furniture moves), lets
the user drop named pins, and marks off-limit zones. Amendment A3: zones are
hard boundaries — Meemoo never enters, and anything accidentally captured
inside one is purged with an audit row. Photos are context for Meemoo's map,
not surveillance: they stay on the base station and are deletable in Studio.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from meemoo.core.models.base import Base, CreatedAtMixin

#: Guided capture target per room (Amendment A6).
ROOM_PHOTO_TARGET = 20


class OnboardingRecord(Base, CreatedAtMixin):
    """One row per device tracking setup progress; absent = never started."""

    __tablename__ = "onboarding_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id"), nullable=False, unique=True, index=True
    )
    # "house" | "apartment" | "senior_room" | "hospital_room" (Amendment A6).
    dwelling_type: Mapped[str | None] = mapped_column(String(30))
    step: Mapped[str] = mapped_column(String(30), nullable=False, default="place")
    completed_at: Mapped[datetime | None] = mapped_column()


class RoomCapture(Base, CreatedAtMixin):
    """One captured room photo, stored under the device-scoped media dir.

    ``x``/``y`` is the room-center location tag on the floor plan (when the
    room matches a plan room) — the hook the A3 auto-purge rule keys on.
    """

    __tablename__ = "room_captures"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    room: Mapped[str] = mapped_column(String(120), nullable=False)
    path: Mapped[str] = mapped_column(String(400), nullable=False)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)


class NoGoZoneRow(Base, CreatedAtMixin):
    """An off-limit zone rectangle on the floor plan (Amendment A3)."""

    __tablename__ = "no_go_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    w: Mapped[float] = mapped_column(Float, nullable=False)
    h: Mapped[float] = mapped_column(Float, nullable=False)
    # "bathroom" (default-prompted) | "user" (drawn by hand).
    reason: Mapped[str] = mapped_column(String(60), nullable=False, default="user")
