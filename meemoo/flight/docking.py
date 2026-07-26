"""Base-station docking state machine (research/06 §G, PX4-precland shaped).

FLYING → DOCK_REQUESTED → TRANSIT (1.5 m standoff on the dock axis) → ALIGN
(hover, null NOSE lateral, settle) → FINAL_APPROACH (pursuit of the mouth,
abort gates) → CAPTURE_PENDING (held slide thrust + magnet) → CAPTURED →
CHARGING → CHARGE_COMPLETE → RELEASE → DEPARTED → FLYING, with ABORT back to
standoff + retry counter and DOCK_FAILED after ``max_attempts``.

Runs base-station-side against telemetry only: the coarse room pose (σ 5 cm),
the dock camera's :class:`RelativePose` (20 Hz, ``tracking_age_ms`` guards a
stale-estimate crash — the PX4 ``PLD_BTOUT`` analogue), and the two-signal
:class:`CaptureTelemetry`. Commands cross a ~100 ms radio latency; slow
dynamics is the gift of this platform (research/04 §F). The control laws
live in docking_laws.py, with the measured failure modes annotated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from meemoo.flight.constants import DockConfig, PhysicsConfig
from meemoo.flight.docking_laws import ApproachLaws
from meemoo.flight.floorplan import DockPose
from meemoo.flight.nav import WorldNav
from meemoo.flight.types import (
    APPROACH_PHASES,
    CaptureTelemetry,
    DockPhase,
    Pose,
    RelativePose,
    ThrustCommand,
)

_TIMEOUT_S: dict[DockPhase, float] = {
    DockPhase.TRANSIT: 90.0,
    DockPhase.ALIGN: 30.0,
    DockPhase.FINAL_APPROACH: 40.0,
    DockPhase.CAPTURE_PENDING: 15.0,
}


@dataclass(slots=True)
class DockingOutput:
    """One control tick: thrust + dock-side commands + phase transitions."""

    cmd: ThrustCommand
    retention: bool
    charge_enabled: bool
    transitions: list[tuple[DockPhase, DockPhase]] = field(default_factory=list)


@dataclass(slots=True)
class _AxisErrors:
    """Nose errors in the dock frame (m), from the best available source."""

    range_m: float  # out along the approach axis (0 = mouth plane)
    lateral_m: float
    vertical_m: float
    v_axis_mps: float  # positive = closing on the mouth
    v_lat_mps: float
    fresh: bool  # True when from a live camera fix


class DockingController(ApproachLaws):
    """Deterministic docking state machine. No model anywhere near it."""

    def __init__(
        self,
        phys_cfg: PhysicsConfig,
        dock_cfg: DockConfig,
        dock_pose: DockPose,
        *,
        nav: WorldNav | None = None,
        max_attempts: int = 6,
        standoff_m: float = 1.5,
    ) -> None:
        self.phys_cfg = phys_cfg
        self.dock_cfg = dock_cfg
        self.dock_pose = dock_pose
        self.nav = nav or WorldNav(phys_cfg)
        self.max_attempts = max_attempts
        self.standoff_m = standoff_m
        self.phase = DockPhase.FLYING
        self.retries = 0
        self._phase_t = 0.0
        self._settle_t = 0.0
        self._steer_i = 0.0  # crab-angle integrator (path following)
        # EMA-filtered settle signals: judging a noisy pose sample-by-sample
        # never strings enough consecutive "good" samples together
        self._ema_dist = 1.0
        self._ema_speed = 1.0
        self._ema_lat = 1.0
        self._ema_pm = 0.0  # smoothed predicted miss at the mouth plane
        self._stale_t = 0.0  # camera-loss grace timer (dead-reckon briefly)
        self._buoy_ff_gf = 0.0  # netBuoyancy telemetry feedforward
        self._hold_pt: tuple[float, float] | None = None  # pirouette anchor
        self._transitions: list[tuple[DockPhase, DockPhase]] = []
        ax, ay = dock_pose.axis
        self._axis = (ax, ay)
        self._axis_angle = math.atan2(ay, ax)
        self._approach_heading = math.atan2(-ay, -ax)  # nose INTO the mouth
        self._standoff = (dock_pose.x + ax * standoff_m, dock_pose.y + ay * standoff_m)

    # -------------------------------------------------------------- commands
    def request_dock(self) -> None:
        if self.phase in (DockPhase.FLYING, DockPhase.DEPARTED, DockPhase.DOCK_FAILED):
            self.retries = 0
            self._enter(DockPhase.DOCK_REQUESTED)

    def abort(self) -> None:
        if self.phase in APPROACH_PHASES:
            self._enter(DockPhase.ABORT)

    def request_undock(self) -> None:
        if self.phase in (DockPhase.CAPTURED, DockPhase.CHARGING,
                          DockPhase.CHARGE_COMPLETE):
            self._enter(DockPhase.RELEASE)

    @property
    def docked(self) -> bool:
        return self.phase in (DockPhase.CAPTURED, DockPhase.CHARGING,
                              DockPhase.CHARGE_COMPLETE)

    # ------------------------------------------------------------------ tick
    def drive(
        self,
        pose: Pose,
        relpose: RelativePose,
        capture: CaptureTelemetry,
        battery_pct: float,
        dt: float,
        *,
        buoyancy_est_gf: float = 0.0,
    ) -> DockingOutput:
        """One control tick. ``buoyancy_est_gf`` is the hover-duty-derived
        netBuoyancy telemetry (research/06 §G): it feeds the vertical
        channel forward so a ±5 gf trim error cannot eat the capture radius
        while the slow integrator catches up."""
        self._phase_t += dt
        self._buoy_ff_gf = buoyancy_est_gf
        err = self._errors(pose, relpose)
        cmd = ThrustCommand()
        retention = self.docked or self.phase is DockPhase.CAPTURE_PENDING
        charge = self.phase in (DockPhase.CHARGING, DockPhase.CHARGE_COMPLETE)

        if self.phase is DockPhase.DOCK_REQUESTED:
            self.nav.reset_integrators()
            self._enter(DockPhase.TRANSIT)
        elif self.phase is DockPhase.TRANSIT:
            cmd = self._goto_standoff(pose, dt)
            if self.nav.arrived(pose, *self._standoff3()):
                self._enter(DockPhase.ALIGN)
        elif self.phase is DockPhase.ALIGN:
            cmd = self._align(pose, err, dt)
        elif self.phase is DockPhase.FINAL_APPROACH:
            cmd = self._approach(pose, err, dt)
        elif self.phase is DockPhase.CAPTURE_PENDING:
            cmd = self._capture_pending(pose, err, capture, dt)
        elif self.phase is DockPhase.CAPTURED:
            self._enter(DockPhase.CHARGING)
        elif self.phase is DockPhase.CHARGING:
            if battery_pct >= 99.9:
                self._enter(DockPhase.CHARGE_COMPLETE)
        elif self.phase is DockPhase.RELEASE:
            retention = False
            charge = False
            cmd = self._release(pose, err, capture)
        elif self.phase is DockPhase.ABORT:
            cmd = self._recover(pose, dt)

        if self.phase in _TIMEOUT_S and self._phase_t > _TIMEOUT_S[self.phase]:
            self._enter(DockPhase.ABORT)
        transitions, self._transitions = self._transitions, []
        return DockingOutput(cmd, retention, charge, transitions)

    # -------------------------------------------------------------- recovery
    def _recover(self, pose: Pose, dt: float) -> ThrustCommand:
        cmd = self._goto_standoff(pose, dt)
        sx, sy, sz = self._standoff3()
        a = min(1.0, dt / 0.3)
        d3 = math.hypot(sx - pose.x, sy - pose.y) + max(0.0, abs(sz - pose.z) - 0.10)
        self._ema_dist += (d3 - self._ema_dist) * a
        self._ema_speed += (math.hypot(pose.vx, pose.vy) - self._ema_speed) * a
        recovered = self._ema_dist < 0.35 and self._ema_speed < 0.16
        if recovered or self._phase_t > 25.0:
            self.retries += 1
            if self.retries >= self.max_attempts:
                self._enter(DockPhase.DOCK_FAILED)
            else:
                self.nav.reset_integrators()
                self._enter(DockPhase.ALIGN)
        return cmd

    # ----------------------------------------------------------------- state
    def _enter(self, phase: DockPhase) -> None:
        prev = self.phase
        self.phase = phase
        self._phase_t = 0.0
        self._settle_t = 0.0
        if phase is DockPhase.FINAL_APPROACH:
            # seed the crab integrator from the draft trim ALIGN just learned
            # (+δ steers force toward −l_hat, so δ carries the OPPOSITE sign
            # of the lateral trim force the integrators hold)
            ax, ay = self._axis
            lat_gf = -self.nav.ix * ay + self.nav.iy * ax
            self._steer_i = min(0.5, max(-0.5, math.atan2(-lat_gf, 5.0)))
            self._ema_pm = 0.0
            self._stale_t = 0.0
            self._hold_pt = None
        if phase in (DockPhase.ALIGN, DockPhase.ABORT, DockPhase.TRANSIT):
            self.nav.reset_hover()
            self._ema_dist = 1.0
            self._ema_speed = 1.0
            self._ema_lat = 1.0
        self._transitions.append((prev, phase))

    def _standoff3(self) -> tuple[float, float, float]:
        return (self._standoff[0], self._standoff[1], self.dock_pose.z)
