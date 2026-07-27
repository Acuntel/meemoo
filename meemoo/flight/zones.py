"""Off-limit zones (Amendment A3): geometry + route filtering.

A zone is a hard boundary, not a preference: Meemoo never plans a route
through one, and a goto into one is refused with a ``flight.refused`` event
instead of flown. The sim holds the active zone list (pushed from the DB by
whoever wires the app — Art. II §2 keeps flight ignorant of storage).
"""

from __future__ import annotations

from dataclasses import dataclass

#: (label, kind, x, y) — the sim's route tuple shape.
RouteTuple = tuple[str, str, float, float]


@dataclass(frozen=True, slots=True)
class Zone:
    """An axis-aligned off-limit rectangle on the floor plan (meters)."""

    name: str
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h


def zone_containing(zones: list[Zone], x: float, y: float) -> Zone | None:
    """The first zone containing the point, or None."""
    for zone in zones:
        if zone.contains(x, y):
            return zone
    return None


def refusal_payload(
    device_id: int, zone: Zone, *, label: str, x: float, y: float
) -> dict[str, object]:
    """Payload for a ``flight.refused`` event (plain, honest wording)."""
    return {
        "device_id": device_id,
        "reason": f"{zone.name} is off limits, so Meemoo stays out",
        "zone": zone.name,
        "label": label,
        "x": x,
        "y": y,
    }


def split_route(
    zones: list[Zone], device_id: int, waypoints: list[RouteTuple]
) -> tuple[list[RouteTuple], list[dict[str, object]]]:
    """Partition a route into flyable waypoints and refusal payloads."""
    allowed: list[RouteTuple] = []
    refusals: list[dict[str, object]] = []
    for wp in waypoints:
        label, _kind, x, y = wp
        zone = zone_containing(zones, x, y)
        if zone is None:
            allowed.append(wp)
        else:
            refusals.append(refusal_payload(device_id, zone, label=label, x=x, y=y))
    return allowed, refusals
