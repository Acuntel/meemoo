"""Declarative base + shared column helpers for all Meemoo models.

Every table is keyed by ``device_id`` (fleet-ready from day one — a facility
running 20 blimps is the same software).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Timezone-aware UTC now (SQLite stores naive; we always write UTC)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Project-wide declarative base."""

    type_annotation_map = {dict[str, object]: JSON}


class CreatedAtMixin:
    """Adds a ``created_at`` UTC timestamp column."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
