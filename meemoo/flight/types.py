"""Shared flight/dock types: docking phases, telemetry, commands.

The telemetry shapes follow research/06 §G exactly — relative pose from the
dock camera (base-station side, never the aircraft), two independent capture
channels, charge state, and the LTA-specific ``net_buoyancy_gf`` derived from
hover-thrust duty.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class DockPhase(StrEnum):
    """Docking state machine (research/06 §G, PX4 precland structure)."""

    FLYING = "FLYING"
    DOCK_REQUESTED = "DOCK_REQUESTED"
    TRANSIT = "TRANSIT"
    ALIGN = "ALIGN"
    FINAL_APPROACH = "FINAL_APPROACH"
    CAPTURE_PENDING = "CAPTURE_PENDING"
    CAPTURED = "CAPTURED"
    CHARGING = "CHARGING"
    CHARGE_COMPLETE = "CHARGE_COMPLETE"
    RELEASE = "RELEASE"
    DEPARTED = "DEPARTED"
    ABORT = "ABORT"
    DOCK_FAILED = "DOCK_FAILED"


APPROACH_PHASES = frozenset(
    {DockPhase.TRANSIT, DockPhase.ALIGN, DockPhase.FINAL_APPROACH, DockPhase.CAPTURE_PENDING}
)


@dataclass(slots=True)
class ThrustCommand:
    """Base-station motor command (what the radio link will carry).

    ``forward_gf``/``yaw_gf`` share the differential forward pair, so their
    sum saturates per motor — the mixer in physics.py enforces it honestly.
    """

    forward_gf: float = 0.0
    vertical_gf: float = 0.0
    yaw_gf: float = 0.0  # differential component (right minus left, per motor)


@dataclass(frozen=True, slots=True)
class Pose:
    """World-frame pose (coarse room tracking — σ ~5 cm)."""

    x: float
    y: float
    z: float
    heading_rad: float
    vx: float
    vy: float
    vz: float
    yaw_rate: float
    swing_rad: float
    swing_rate: float
    t: float


@dataclass(frozen=True, slots=True)
class RelativePose:
    """Dock-camera relative pose (research/06 §G telemetry, exact fields)."""

    lateral_error_mm: float
    vertical_error_mm: float
    range_to_throat_mm: float
    yaw_error_deg: float
    tracking_valid: bool
    tracking_age_ms: float

    @property
    def radial_error_mm(self) -> float:
        return math.hypot(self.lateral_error_mm, self.vertical_error_mm)


@dataclass(frozen=True, slots=True)
class CaptureTelemetry:
    """Two independent capture channels — never confirm on one alone."""

    retention_engaged: bool
    contact_continuity: bool
    capture_switch: bool

    @property
    def confirmed(self) -> bool:
        """Constitution Art. II §3: contact continuity AND hall/reed switch.

        Vision cannot distinguish "docked" from "resting against the cone";
        a single electrical signal can be a smudged ring. Two channels or it
        did not happen.
        """
        return self.contact_continuity and self.capture_switch


@dataclass(frozen=True, slots=True)
class ChargeTelemetry:
    charge_current_ma: float
    pack_voltage_mv: float
    pack_temp_c: float
    charge_state: str  # none | bulk | topping | complete | fault
    charge_fault_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BatteryStatus:
    pct: float
    charging: bool
    minutes_remaining: float


@dataclass(slots=True)
class SimSnapshot:
    """Sprite/rendering stream for the web sim (step-07 consumes this)."""

    t: float
    x: float
    y: float
    z: float
    heading_deg: float
    swing_deg: float
    phase: str
    battery_pct: float
    charging: bool
    docked: bool
    net_buoyancy_gf: float
    helium_level_pct: float
    retries: int
    plan_name: str
    waypoint_label: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "t": round(self.t, 2),
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "heading_deg": round(self.heading_deg, 1),
            "swing_deg": round(self.swing_deg, 2),
            "phase": self.phase,
            "battery_pct": round(self.battery_pct, 1),
            "charging": self.charging,
            "docked": self.docked,
            "net_buoyancy_gf": round(self.net_buoyancy_gf, 2),
            "helium_level_pct": round(self.helium_level_pct, 2),
            "retries": self.retries,
            "plan_name": self.plan_name,
            "waypoint_label": self.waypoint_label,
        }


def wrap_angle(a: float) -> float:
    """Wrap to (-pi, pi]."""
    while a <= -math.pi:
        a += 2.0 * math.pi
    while a > math.pi:
        a -= 2.0 * math.pi
    return a
