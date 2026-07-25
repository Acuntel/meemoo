"""Flight tables: routes + waypoints, and dock telemetry snapshots.

The dock is its own device beside the blimp (Constitution Art. II §3):
load-cell trim, helium level, and charge state live in the data model NOW
because helium logistics is the physical subscription (Art. VII §5).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from meemoo.core.models.base import Base, CreatedAtMixin, utcnow


class Route(Base, CreatedAtMixin):
    """A named ordered set of waypoints (a 'round')."""

    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Waypoint(Base):
    """One stop on a route; ``kind='person'`` triggers a REAL voice check-in."""

    __tablename__ = "waypoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="area")
    label: Mapped[str | None] = mapped_column(String(120))
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"))


class DockTelemetry(Base):
    """Dock snapshot: load-cell trim, helium level, charge state.

    ``net_buoyancy_gf`` target trim is 2–4 g NEGATIVE (Art. IV §6) — loss of
    power must mean a slow gentle descent, never a ceiling-parked failure.
    """

    __tablename__ = "dock_telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, index=True)
    net_buoyancy_gf: Mapped[float | None] = mapped_column(Float)
    load_cell_g: Mapped[float | None] = mapped_column(Float)
    helium_level_pct: Mapped[float | None] = mapped_column(Float)
    charging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    battery_pct: Mapped[float | None] = mapped_column(Float)
