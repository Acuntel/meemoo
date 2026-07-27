"""Voice motion commands executed on the aircraft (Amendment A5).

Split out of mission.py (Art. IX file-size law); the class state lives on
:class:`~meemoo.flight.sim_blimp.SimulatedBlimp`, which mixes this in beside
:class:`~meemoo.flight.mission.MissionMixin`.

Typed ``flight.command`` payloads arrive from the voice layer and become
halt / drift / come-here / goto / spin against the same honest physics as
every other flight. Two rules never bend here: an off-limit zone still wins
(Amendment A3), and a dock capture in progress is allowed to finish
(Art. II §3).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from meemoo.core import topics
from meemoo.flight.capabilities import FlightCommand, MotionKind
from meemoo.flight.mission import Emission, FlightMode
from meemoo.flight.types import DockPhase, Pose, ThrustCommand
from meemoo.flight.zones import refusal_payload, zone_containing

if TYPE_CHECKING:
    from meemoo.flight.constants import PhysicsConfig
    from meemoo.flight.docking import DockingController
    from meemoo.flight.floorplan import FloorPlan
    from meemoo.flight.nav import WorldNav
    from meemoo.flight.physics import BlimpPhysics
    from meemoo.flight.zones import Zone

logger = logging.getLogger(__name__)

NUDGE_M = 0.75  # one "go left" drift step
NUDGE_Z_M = 0.30  # one "go up" / "go down" step
SPIN_S = 5.0  # trick spin duration: about one full turn at SPIN_RATE
SPIN_RATE_RAD_S = 1.6  # ~92 deg/s — visible, and gentle enough to watch
SPIN_YAW_KP = 12.0  # gram-force per rad/s of yaw-rate error
BRAKE_LEAD_S = 0.6  # how far ahead a halt aims, ≈ one nav velocity time constant

#: Dock phases a "stop" may cancel; capture/release must finish (Art. II §3).
_CANCELABLE_DOCK = frozenset({
    DockPhase.DOCK_REQUESTED, DockPhase.TRANSIT, DockPhase.ALIGN,
    DockPhase.FINAL_APPROACH, DockPhase.ABORT,
})


class MotionCommandsMixin:
    """The A5 command executor: stop, drift, come here, go to a pin, spin."""

    if TYPE_CHECKING:  # state provided by SimulatedBlimp
        cfg: PhysicsConfig
        phys: BlimpPhysics
        nav: WorldNav
        docking: DockingController
        plan: FloorPlan
        mode: FlightMode
        device_id: int
        no_go_zones: list[Zone]
        _pending_emissions: list[Emission]
        _pending_round: list[tuple[str, str, float, float]] | None
        _route: list[tuple[str, str, float, float]]
        _route_idx: int
        _hold_until: float
        _hold_target: tuple[float, float, float]
        _spin_until: float
        _spin_anchor: tuple[float, float, float]
        _manual_until: float

        def hold(self) -> None: ...
        def return_to_dock(self) -> None: ...
        def goto(self, x: float, y: float, *, label: str | None = None) -> bool: ...

    # --------------------------------------------------------- bus entry
    def on_command(self, payload: dict[str, object]) -> None:
        """Bus entry: a ``flight.command`` payload for this device."""
        cmd = FlightCommand.from_payload(payload)
        if cmd is None or cmd.device_id != self.device_id:
            return
        accepted = self.execute_command(cmd)
        logger.info(
            "flight: voice command %s %s",
            cmd.command, "accepted" if accepted else "refused",
        )

    def execute_command(self, cmd: FlightCommand) -> bool:
        """Execute a typed flight command; True when motion was accepted."""
        if cmd.command == MotionKind.STOP:
            self.halt()
            return True
        if cmd.command == MotionKind.MOVE:
            return self.nudge(cmd.direction or "")
        if cmd.command == MotionKind.COME_HERE:
            return self.come_here()
        if cmd.command == MotionKind.GOTO:
            if cmd.x is None or cmd.y is None:
                return False
            return self.goto(cmd.x, cmd.y, label=cmd.label)
        if cmd.command == MotionKind.SPIN:
            return self.trick_spin()
        if cmd.command == MotionKind.DOCK:
            self.return_to_dock()
            return True
        return False

    # -------------------------------------------------------------- stop
    def halt(self) -> None:
        """Hard stop (A5): mission cleared NOW; braking starts next cycle."""
        self._route = []
        self._route_idx = 0
        self._hold_until = 0.0
        self._pending_round = None
        self._spin_until = 0.0
        self._manual_until = 0.0  # manual sliders released too (Flight Test STOP)
        if self.mode in (FlightMode.DOCKED, FlightMode.LANDED):
            return  # already still
        if self.mode in (FlightMode.UNDOCKING, FlightMode.RETURNING):
            if self.docking.phase not in _CANCELABLE_DOCK:
                return  # capture/release is finishing: let the dock complete
            self.docking.phase = DockPhase.FLYING  # cancel the approach
        self.hold()
        self._hold_target = self._braking_point()

    def _braking_point(self) -> tuple[float, float, float]:
        """Where the aircraft can actually come to rest, one coast away.

        Braking onto the spot where the word was heard would mean flying
        BACKWARDS after being told to stop. Added mass means it still coasts
        a little; pretending otherwise would be a dishonest sim (Art. II §4).
        """
        x0, y0, x1, y1 = self.plan.bounds
        pad = self.cfg.diameter_m / 2.0
        p = self.phys
        tx = min(x1 - pad, max(x0 + pad, p.x + p.vx * BRAKE_LEAD_S))
        ty = min(y1 - pad, max(y0 + pad, p.y + p.vy * BRAKE_LEAD_S))
        tz = min(self.cfg.ceiling_m, max(0.0, p.z + p.vz * BRAKE_LEAD_S))
        if zone_containing(self.no_go_zones, tx, ty) is not None:
            return (p.x, p.y, p.z)  # never coast into an off-limit zone (A3)
        return (tx, ty, tz)

    # ------------------------------------------------------------- drift
    def nudge(self, direction: str) -> bool:
        """One gentle drift step. Left/right are Meemoo's own left/right."""
        if self.mode not in (FlightMode.ROUND, FlightMode.GOTO, FlightMode.HOLD):
            return False  # docked/landed/mid-dock: the voice layer declines
        x, y, z = self.phys.x, self.phys.y, self._nudge_base_z()
        if direction == "up":
            target = (x, y, min(self.cfg.ceiling_m - 0.15, z + NUDGE_Z_M))
        elif direction == "down":
            target = (x, y, max(0.4, z - NUDGE_Z_M))
        elif direction in ("left", "right"):
            ang = self.phys.heading + (
                math.pi / 2.0 if direction == "left" else -math.pi / 2.0
            )
            x0, y0, x1, y1 = self.plan.bounds
            pad = self.cfg.diameter_m / 2.0
            tx = min(x1 - pad, max(x0 + pad, x + NUDGE_M * math.cos(ang)))
            ty = min(y1 - pad, max(y0 + pad, y + NUDGE_M * math.sin(ang)))
            zone = zone_containing(self.no_go_zones, tx, ty)
            if zone is not None:
                self._pending_emissions.append((topics.FLIGHT_REFUSED, refusal_payload(
                    self.device_id, zone, label=f"drift {direction}", x=tx, y=ty,
                )))
                return False
            target = (tx, ty, z)
        else:
            return False
        self._route = []
        self._route_idx = 0
        self._spin_until = 0.0
        self._hold_target = target
        self.mode = FlightMode.HOLD
        return True

    def _nudge_base_z(self) -> float:
        if self.mode is FlightMode.HOLD:
            return self._hold_target[2]
        return min(self.cfg.ceiling_m - 0.15, max(0.4, self.phys.z))

    # ------------------------------------------------------ come + tricks
    def come_here(self) -> bool:
        """Fly to the person (sim: the nearest person waypoint on the plan)."""
        wps = self.plan.person_waypoints()
        if not wps:
            return False
        near = min(wps, key=lambda w: math.hypot(w.x - self.phys.x, w.y - self.phys.y))
        return self.goto(near.x, near.y, label=near.label or "you")

    def trick_spin(self) -> bool:
        """A gentle in-place spin (A5 tricks); the mission resumes after."""
        if self.mode not in (FlightMode.ROUND, FlightMode.GOTO, FlightMode.HOLD):
            return False
        self._spin_until = self.phys.t + SPIN_S
        self._spin_anchor = (self.phys.x, self.phys.y, self.phys.z)
        self._pending_emissions.append((topics.FLIGHT_STATE, {
            "device_id": self.device_id, "phase": "TRICK_SPIN",
        }))
        return True

    def spin_command(self, pose: Pose, dt: float) -> ThrustCommand:
        """Hold the anchor point while yawing at a fixed, gentle rate."""
        ax, ay, az = self._spin_anchor
        _fx, _fy, fz = self.nav.goto_force(pose, ax, ay, az, dt)
        clamp = self.nav.gains.yaw_clamp_gf
        yaw_gf = SPIN_YAW_KP * (SPIN_RATE_RAD_S - pose.yaw_rate)
        return ThrustCommand(
            forward_gf=0.0, vertical_gf=fz,
            yaw_gf=min(clamp, max(-clamp, yaw_gf)),
        )
