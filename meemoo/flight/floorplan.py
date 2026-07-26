"""JSON floor plans: rooms, dock pose, vents, default waypoints.

Ships a default apartment and a facility wing (MASTER_PROMPT §5). Rooms are
rendering/labelling data for the web sim; the physics uses ``bounds`` (soft
walls), the dock pose, and the vent fields. Plans live in
``meemoo/flight/plans/*.json`` and are trivially user-editable.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

BUILTIN_PLANS = ("apartment", "facility_wing")


@dataclass(frozen=True, slots=True)
class Room:
    name: str
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True, slots=True)
class Vent:
    """A steady directional HVAC outflow near a register (few gf inside radius)."""

    x: float
    y: float
    dir_rad: float
    force_gf: float
    radius_m: float


@dataclass(frozen=True, slots=True)
class DockPose:
    x: float
    y: float
    z: float
    heading_rad: float  # approach axis pointing OUT of the mouth into the room

    @property
    def axis(self) -> tuple[float, float]:
        return (math.cos(self.heading_rad), math.sin(self.heading_rad))


@dataclass(frozen=True, slots=True)
class PlanWaypoint:
    label: str
    kind: str  # "person" | "area" | "door"
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class FloorPlan:
    name: str
    bounds: tuple[float, float, float, float]  # x0, y0, x1, y1 (meters)
    rooms: tuple[Room, ...]
    dock: DockPose
    vents: tuple[Vent, ...]
    waypoints: tuple[PlanWaypoint, ...]

    def standoff(self, distance_m: float = 1.5) -> tuple[float, float]:
        """The point ``distance_m`` out from the dock mouth along its axis."""
        ax, ay = self.dock.axis
        return (self.dock.x + ax * distance_m, self.dock.y + ay * distance_m)

    def person_waypoints(self) -> tuple[PlanWaypoint, ...]:
        return tuple(w for w in self.waypoints if w.kind == "person")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "bounds": list(self.bounds),
            "rooms": [
                {"name": r.name, "x": r.x, "y": r.y, "w": r.w, "h": r.h} for r in self.rooms
            ],
            "dock": {
                "x": self.dock.x,
                "y": self.dock.y,
                "z": self.dock.z,
                "heading_deg": math.degrees(self.dock.heading_rad),
            },
            "waypoints": [
                {"label": w.label, "kind": w.kind, "x": w.x, "y": w.y} for w in self.waypoints
            ],
        }


def _parse(name: str, raw: dict[str, object]) -> FloorPlan:
    bounds_raw = raw["bounds"]
    assert isinstance(bounds_raw, list) and len(bounds_raw) == 4
    dock_raw = raw["dock"]
    assert isinstance(dock_raw, dict)
    rooms_raw = raw.get("rooms", [])
    vents_raw = raw.get("vents", [])
    wps_raw = raw.get("waypoints", [])
    assert isinstance(rooms_raw, list) and isinstance(vents_raw, list)
    assert isinstance(wps_raw, list)
    return FloorPlan(
        name=str(raw.get("name", name)),
        bounds=(
            float(bounds_raw[0]),
            float(bounds_raw[1]),
            float(bounds_raw[2]),
            float(bounds_raw[3]),
        ),
        rooms=tuple(
            Room(str(r["name"]), float(r["x"]), float(r["y"]), float(r["w"]), float(r["h"]))
            for r in rooms_raw
        ),
        dock=DockPose(
            x=float(dock_raw["x"]),
            y=float(dock_raw["y"]),
            z=float(dock_raw.get("z", 1.2)),
            heading_rad=math.radians(float(dock_raw.get("heading_deg", 0.0))),
        ),
        vents=tuple(
            Vent(
                float(v["x"]),
                float(v["y"]),
                math.radians(float(v.get("dir_deg", 0.0))),
                float(v.get("force_gf", 2.0)),
                float(v.get("radius_m", 1.0)),
            )
            for v in vents_raw
        ),
        waypoints=tuple(
            PlanWaypoint(str(w["label"]), str(w.get("kind", "area")), float(w["x"]), float(w["y"]))
            for w in wps_raw
        ),
    )


def load_plan(name_or_path: str = "apartment") -> FloorPlan:
    """Load a built-in plan by name or any plan by JSON path."""
    path = Path(name_or_path)
    if path.suffix == ".json" and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        return _parse(path.stem, data)
    if name_or_path not in BUILTIN_PLANS:
        raise ValueError(f"unknown floor plan {name_or_path!r}; built-ins: {BUILTIN_PLANS}")
    ref = resources.files("meemoo.flight.plans").joinpath(f"{name_or_path}.json")
    data = json.loads(ref.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return _parse(name_or_path, data)
