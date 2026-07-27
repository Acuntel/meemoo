"""Mission layer for SimulatedBlimp: modes, route progress, battery watch.

Split out of sim_blimp.py (Art. IX file-size law); the class state lives on
:class:`~meemoo.flight.sim_blimp.SimulatedBlimp`, which mixes this in. The
voice motion commands that interrupt a mission live beside it in
:mod:`meemoo.flight.commands`.
"""

from __future__ import annotations

import logging
import math
from enum import StrEnum
from typing import TYPE_CHECKING

from meemoo.core import topics
from meemoo.flight.types import Pose, ThrustCommand

if TYPE_CHECKING:
    from meemoo.flight.constants import PhysicsConfig
    from meemoo.flight.docking import DockingController
    from meemoo.flight.floorplan import FloorPlan
    from meemoo.flight.nav import WorldNav
    from meemoo.flight.physics import BlimpPhysics
    from meemoo.flight.types import BatteryStatus

logger = logging.getLogger(__name__)

Emission = tuple[str, dict[str, object]]


class FlightMode(StrEnum):
    DOCKED = "DOCKED"
    UNDOCKING = "UNDOCKING"
    ROUND = "ROUND"
    GOTO = "GOTO"
    HOLD = "HOLD"
    RETURNING = "RETURNING"
    LANDED = "LANDED"


class MissionMixin:
    """Route flying + waypoint dwell + battery watch."""

    if TYPE_CHECKING:  # state provided by SimulatedBlimp
        cfg: PhysicsConfig
        phys: BlimpPhysics
        nav: WorldNav
        docking: DockingController
        plan: FloorPlan
        mode: FlightMode
        device_id: int
        person_hold_s: float
        area_hold_s: float
        _route: list[tuple[str, str, float, float]]
        _route_idx: int
        _hold_until: float
        _hold_target: tuple[float, float, float]
        _spin_until: float
        _spin_anchor: tuple[float, float, float]
        _last_battery_emit: float
        _low_battery_fired: bool

        def hold(self) -> None: ...
        def return_to_dock(self) -> None: ...
        def battery_status(self) -> BatteryStatus: ...
        def spin_command(self, pose: Pose, dt: float) -> ThrustCommand: ...

    # ------------------------------------------------------------- flying
    def _fly(self, pose: Pose, dt: float) -> ThrustCommand:
        if self.phys.t < self._spin_until:  # trick spin overrides, then resumes
            return self.spin_command(pose, dt)
        if self.mode in (FlightMode.ROUND, FlightMode.GOTO) and self._route_idx < len(
            self._route
        ):
            label, kind, x, y = self._route[self._route_idx]
            z = 0.12 if kind == "land" else 1.2
            return self._goto(pose, x, y, z, dt)
        if self.mode is FlightMode.LANDED:
            return ThrustCommand()
        tx, ty, tz = self._hold_target
        return self._goto(pose, tx, ty, tz, dt)

    def _goto(self, pose: Pose, x: float, y: float, z: float, dt: float) -> ThrustCommand:
        """Cruise nose-first; hover bidirectionally near the target (chasing
        the force vector with the nose orbits the point — see nav.py)."""
        far = math.hypot(x - pose.x, y - pose.y) > 0.5
        v_max = None if far else 0.22
        f = self.nav.goto_force(pose, x, y, z, dt, v_max=v_max)
        return self.nav.force_to_command(pose, *f, bidirectional=not far, dt=dt)

    # ----------------------------------------------------------- waypoints
    def _mode_progress(self) -> list[Emission]:
        if self.mode not in (FlightMode.ROUND, FlightMode.GOTO):
            return []
        if self._route_idx >= len(self._route):
            return []
        label, kind, x, y = self._route[self._route_idx]
        if self._hold_until > 0.0:  # dwelling at the waypoint
            if self.phys.t >= self._hold_until:
                return self._advance_route()
            return []
        z = 0.12 if kind == "land" else 1.2
        if not self.nav.arrived(self.phys.pose(), x, y, z):
            return []
        # arrived: emit, then dwell (person stops hold for the REAL check-in)
        self._hold_until = self.phys.t + (
            self.person_hold_s if kind == "person" else self.area_hold_s
        )
        return [(topics.FLIGHT_WAYPOINT_REACHED, {
            "device_id": self.device_id, "waypoint": label, "kind": kind,
            "x": x, "y": y,
        })]

    def _advance_route(self) -> list[Emission]:
        label, kind, _, _ = self._route[self._route_idx]
        self._hold_until = 0.0
        self._route_idx += 1
        if kind == "land":
            self.phys.motors_on = False
            self.mode = FlightMode.LANDED
            return [(topics.FLIGHT_LANDED,
                     {"device_id": self.device_id, "where": "floor"})]
        if self._route_idx >= len(self._route):
            if self.mode is FlightMode.ROUND:
                self.return_to_dock()
            else:
                self.hold()
        return []

    # ------------------------------------------------------------- battery
    def _battery_watch(self, dt: float) -> list[Emission]:
        out: list[Emission] = []
        pct = self.phys.battery_pct
        if self.phys.t - self._last_battery_emit >= 5.0:
            self._last_battery_emit = self.phys.t
            out.append((topics.FLIGHT_BATTERY, {
                "device_id": self.device_id, "pct": round(pct, 1),
                "charging": self.battery_status().charging,
            }))
        if (
            pct < self.cfg.auto_return_pct
            and not self._low_battery_fired
            and self.mode in (FlightMode.ROUND, FlightMode.GOTO, FlightMode.HOLD)
        ):
            self._low_battery_fired = True
            logger.warning("flight: battery %.1f%% < %.0f%% — auto-return",
                           pct, self.cfg.auto_return_pct)
            self.return_to_dock()
            out.append((topics.FLIGHT_STATE, {
                "device_id": self.device_id, "phase": "AUTO_RETURN", "battery_pct": pct,
            }))
        if pct >= self.cfg.auto_return_pct:
            self._low_battery_fired = False
        return out
