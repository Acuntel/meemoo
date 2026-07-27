"""Manual slider control (the Flight Test page) against the honest physics.

The Flight Test page posts normalized slider inputs (forward/back, up/down,
turn) at a steady cadence; this mixin turns them into ThrustCommands the
same airframe flies. The exact discipline the firmware link will use
applies here too:

- Input EXPIRES (``MANUAL_TTL_S``) — a closed laptop lid or dead socket
  means the aircraft brakes to a hold, the HTTP twin of the MUP/1 packet
  ttl (dumb aircraft: no fresh command, no thrust).
- The 1.3 m/s cap (Amendment A5) is NOT enforced here — it lives in
  physics.step as the governor, so manual thrust simply cannot push past
  it. This layer only reports when the cap is binding so the UI can say so.
- Off-limit zones stay hard (Amendment A3): a velocity lookahead brakes
  the aircraft before it coasts into one and emits ``flight.refused``
  (rate-limited), exactly as honest as a refused goto.
- No trim assist: sticks at zero means the 2–4 g negative trim sinks the
  aircraft gently, exactly like the real airframe on the leash. Faking a
  free hover here would teach the pilot a lie (Art. II §4).

Split into its own file per the Art. IX size law; state lives on
:class:`~meemoo.flight.sim_blimp.SimulatedBlimp`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from meemoo.core import topics
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

MANUAL_TTL_S = 1.0  # slider input expires; the page re-sends every ~300 ms
ZONE_LOOKAHEAD_S = 3.0  # brake early: reverse props are weak (5 gf/motor)
ZONE_PAD_M = 0.15  # standoff skirt so boundary creep can't nibble inside
REFUSAL_COOLDOWN_S = 2.5  # one honest refusal, not a firehose
_MIN_ALT_M = 0.35  # manual flying floor: below this the vertical stick only lifts
_YAW_DEADBAND = 0.02
_BRAKE_ASK_GF = 40.0  # ask big; nav._finish clamps to the honest per-motor caps

#: Dock phases manual control may cancel (mirror of commands.py — capture
#: and release always finish, Art. II §3).
_CANCELABLE_DOCK = frozenset({
    DockPhase.DOCK_REQUESTED, DockPhase.TRANSIT, DockPhase.ALIGN,
    DockPhase.FINAL_APPROACH, DockPhase.ABORT,
})


class ManualControlMixin:
    """Slider inputs → thrust, with the same bright lines as every flight."""

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
        _manual_input: tuple[float, float, float]
        _manual_until: float
        _manual_refusal_t: float
        _hold_target: tuple[float, float, float]

        def hold(self) -> None: ...

    def init_manual_state(self) -> None:
        """Called from SimulatedBlimp.__init__ (keeps that file in the size law)."""
        self._manual_input = (0.0, 0.0, 0.0)
        self._manual_until = 0.0
        self._manual_refusal_t = -1e9

    # ----------------------------------------------------------- API entry
    def set_manual_input(
        self, forward: float, vertical: float, yaw: float
    ) -> dict[str, object]:
        """Accept one slider frame; returns an honest accepted/reason dict."""
        if self.mode is FlightMode.DOCKED:
            return {"accepted": False,
                    "reason": "Meemoo is resting on the dock. Lift off first."}
        if self.mode is FlightMode.LANDED:
            return {"accepted": False,
                    "reason": "Meemoo is on the floor. Lift off first."}
        if self.mode in (FlightMode.UNDOCKING, FlightMode.RETURNING):
            if self.docking.phase not in _CANCELABLE_DOCK:
                return {"accepted": False,
                        "reason": "The dock is finishing a capture. One moment."}
            self.docking.phase = DockPhase.FLYING  # cancel the approach

        def clamp(v: float) -> float:
            return max(-1.0, min(1.0, float(v)))

        self._manual_input = (clamp(forward), clamp(vertical), clamp(yaw))
        self._manual_until = self.phys.t + MANUAL_TTL_S
        if self.mode is not FlightMode.MANUAL:
            self.mode = FlightMode.MANUAL
            self._pending_emissions.append((topics.FLIGHT_STATE, {
                "device_id": self.device_id, "phase": "MANUAL",
            }))
        return {"accepted": True, "reason": None}

    def manual_active(self) -> bool:
        return self.mode is FlightMode.MANUAL and self.phys.t <= self._manual_until

    def cap_engaged(self) -> bool:
        """True while the A5 speed governor is the binding constraint."""
        p = self.phys
        speed = math.sqrt(p.vx * p.vx + p.vy * p.vy + p.vz * p.vz)
        return speed >= self.cfg.max_speed_mps * 0.97

    # --------------------------------------------------------------- flying
    def manual_command(self, pose: Pose, dt: float) -> ThrustCommand:
        """One control tick of MANUAL mode (called from mission._fly)."""
        if self.phys.t > self._manual_until:
            # Input expired: brake to a hold, the sim twin of the packet ttl.
            self.hold()
            return self.nav.hover_command(
                pose, pose.x, pose.y, max(_MIN_ALT_M, pose.z), dt
            )
        if self._zone_guard(pose):
            if math.hypot(pose.vx, pose.vy) > 0.15:
                return self._brake(pose, dt)  # still carrying speed: full stop
            tx, ty, tz = self._hold_target
            return self.nav.hover_command(pose, tx, ty, tz, dt)

        fwd_in, vert_in, yaw_in = self._manual_input
        g = self.nav.gains
        fwd_gf = fwd_in * 2.0 * self.cfg.thrust_max_gf_per_motor
        vert_gf = vert_in * 2.0 * self.cfg.thrust_max_gf_per_motor
        if pose.z <= _MIN_ALT_M and vert_gf < 0.0:
            vert_gf = 0.0  # near the deck the vertical stick only lifts
        if abs(yaw_in) > _YAW_DEADBAND:
            yaw_gf = yaw_in * g.yaw_clamp_gf
        else:
            yaw_gf = -g.kd_yaw_gf * pose.yaw_rate  # stick released: damp the spin
        yaw_gf = min(g.yaw_clamp_gf, max(-g.yaw_clamp_gf, yaw_gf))
        # The active swing damper stays on, manual or not (research/04 §F).
        damp = g.swing_damp_gf * pose.swing_rate
        damp = min(g.swing_damp_clamp_gf, max(-g.swing_damp_clamp_gf, damp))
        fwd_gf -= damp
        # Attitude first: leave yaw its per-motor headroom (mixer truth).
        fwd_cap = 2.0 * max(0.0, self.cfg.thrust_max_gf_per_motor - abs(yaw_gf))
        rev_cap = 2.0 * max(0.0, self.cfg.thrust_reverse_gf_per_motor - abs(yaw_gf))
        fwd_gf = min(fwd_cap, max(-rev_cap, fwd_gf))
        return ThrustCommand(forward_gf=fwd_gf, vertical_gf=vert_gf, yaw_gf=yaw_gf)

    def _brake(self, pose: Pose, dt: float) -> ThrustCommand:
        """Max honest deceleration opposing the velocity (nose either pole)."""
        sp = math.hypot(pose.vx, pose.vy)
        fx = -pose.vx / sp * _BRAKE_ASK_GF
        fy = -pose.vy / sp * _BRAKE_ASK_GF
        to_gf = self.cfg.effective_mass_kg / 9.80665e-3
        fz = self.nav.gains.kv_z * (0.0 - pose.vz) * to_gf
        return self.nav.force_to_command(pose, fx, fy, fz, bidirectional=True, dt=dt)

    # ------------------------------------------------------------ zone guard
    def _zone_guard(self, pose: Pose) -> bool:
        """Brake before coasting into an off-limit zone (Amendment A3).

        Returns True when braking is engaged this tick; emits ONE honest
        ``flight.refused`` per cooldown window and pins the hold target at
        the current (legal) position.
        """
        px = pose.x + pose.vx * ZONE_LOOKAHEAD_S
        py = pose.y + pose.vy * ZONE_LOOKAHEAD_S
        zone = zone_containing(self.no_go_zones, px, py)
        if zone is None:
            zone = self._zone_near(pose.x, pose.y)
        if zone is None:
            return False
        self._hold_target = (self.phys.x, self.phys.y, max(_MIN_ALT_M, self.phys.z))
        self._manual_input = (0.0, self._manual_input[1], self._manual_input[2])
        if self.phys.t - self._manual_refusal_t >= REFUSAL_COOLDOWN_S:
            self._manual_refusal_t = self.phys.t
            self._pending_emissions.append((topics.FLIGHT_REFUSED, refusal_payload(
                self.device_id, zone, label="manual drive", x=px, y=py,
            )))
        return True

    def _zone_near(self, x: float, y: float) -> Zone | None:
        """A zone whose padded skirt the aircraft is standing in."""
        for zone in self.no_go_zones:
            if (
                zone.x - ZONE_PAD_M <= x <= zone.x + zone.w + ZONE_PAD_M
                and zone.y - ZONE_PAD_M <= y <= zone.y + zone.h + ZONE_PAD_M
            ):
                return zone
        return None
