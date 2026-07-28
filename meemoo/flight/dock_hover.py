"""Station-keeping laws for the docking machine: standoff, align, hold.

Split out of docking_laws.py (Art. IX §1, files under 300 lines). Everything
here holds a POSITION on the dock axis; docking_laws.py owns the moving legs.

The shared idea, and the one that makes an underactuated blimp dockable: the
funnel judges where the NOSE is, and the nose sits on a 0.3-0.6 m boom, so
the hover target is offset by the boom's yaw geometry rather than the
heading being pinned. A blimp cannot hold position against a lateral draft
with its nose pinned, and the sphere's capture test never asks it to.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from meemoo.flight.types import (
    CaptureTelemetry,
    DockPhase,
    Pose,
    ThrustCommand,
)

if TYPE_CHECKING:
    from meemoo.flight.constants import DockConfig, PhysicsConfig
    from meemoo.flight.dock_plan import ApproachPlanner
    from meemoo.flight.dock_slide import SlideMonitor
    from meemoo.flight.docking import _AxisErrors
    from meemoo.flight.draft import DraftEstimator
    from meemoo.flight.floorplan import DockPose
    from meemoo.flight.nav import WorldNav


class HoverLaws:
    """Mixin: station-keeping. State lives on DockingController."""

    if TYPE_CHECKING:  # attributes provided by DockingController
        nav: WorldNav
        draft: DraftEstimator
        planner: ApproachPlanner
        slide: SlideMonitor
        phys_cfg: PhysicsConfig
        dock_cfg: DockConfig
        dock_pose: DockPose
        standoff_m: float
        replans: int
        _axis: tuple[float, float]
        _axis_angle: float
        _approach_heading: float
        _settle_t: float
        _last_thrust_gf: float
        _nose_lat_f: float
        _no_reenter: bool
        _ema_dist: float
        _ema_speed: float
        _ema_lat: float
        _stale_t: float
        _buoy_ff_gf: float
        _phase_t: float
        _hold_pt: tuple[float, float] | None

        def _enter(self, phase: DockPhase) -> None: ...
        def _abort(self, reason: str) -> None: ...
        def _standoff3(self) -> tuple[float, float, float]: ...

    # ---------------------------------------------------------------- laws
    def _goto_standoff(self, pose: Pose, dt: float) -> ThrustCommand:
        sx, sy, sz = self._standoff3()
        if math.hypot(sx - pose.x, sy - pose.y) > 0.5:
            f = self.nav.goto_force(pose, sx, sy, sz, dt)
            return self.nav.force_to_command(pose, *f, bidirectional=False, dt=dt)
        # Near the point, hand over to the aim-then-hold primitive. Chasing
        # the force vector with the nose ORBITS the target (nav.py documents
        # it, and TRANSIT was still doing it): 20 of 200 2D episodes circled
        # the standoff at 0.3 m and 0.28 m/s until the 90 s phase timeout —
        # an attempt spent before the docking controller ever ran.
        return self.nav.hover_command(
            pose, sx, sy, sz, dt, prefer_heading=self._approach_heading
        )

    def _hover_axis(
        self, pose: Pose, dist_m: float, dt: float
    ) -> tuple[ThrustCommand, float]:
        """Station-keep on the dock axis at ``dist_m``, NOSE on the corridor.

        Heading is NOT forced onto the axis: an underactuated blimp cannot
        hold position against a lateral draft with its nose pinned — the
        sphere's capture test never requires yaw. Instead the hover TARGET
        is offset so that the NOSE (what the camera tracks and the funnel
        judges) sits on the axis for whatever heading the draft demands:
        center_lateral = −arm·sin(heading−axis). Returns the command and the
        3D distance to that target (the settle signal).
        """
        ax, ay = self._axis
        sx = self.dock_pose.x + ax * dist_m
        sy = self.dock_pose.y + ay * dist_m
        sz = self.dock_pose.z
        # The offset follows a SLOW heading: with a 0.585 m boom, feeding the
        # instantaneous heading in makes the hover chase a target that swings
        # half a metre every time the vehicle yaws, and the pair oscillate.
        # The steady-state value is what matters (it is the crab equilibrium
        # — body downwind, boom reaching back onto the corridor), so filter
        # to it over ~1.5 s.
        nose_lat = self.phys_cfg.nose_arm_m * math.sin(
            pose.heading_rad - self._axis_angle
        )
        self._nose_lat_f += (nose_lat - self._nose_lat_f) * min(1.0, dt / 1.5)
        nose_lat = self._nose_lat_f
        tx = sx + ay * nose_lat  # −l_hat · nose_lat, l_hat = (−ay, ax)
        ty = sy - ax * nose_lat
        f = self.nav.goto_force(pose, tx, ty, sz, dt, v_max=0.25)
        cmd = self.nav.force_to_command(
            pose, *f, bidirectional=True, prefer_heading=self._approach_heading, dt=dt
        )
        d3 = math.hypot(tx - pose.x, ty - pose.y) + max(0.0, abs(sz - pose.z) - 0.10)
        return cmd, d3

    def _align(self, pose: Pose, err: _AxisErrors, dt: float) -> ThrustCommand:
        cmd, d3 = self._hover_axis(pose, self.standoff_m, dt)
        a = min(1.0, dt / 0.3)  # ~0.3 s EMA smooths the σ-5 cm pose noise
        self._ema_dist += (d3 - self._ema_dist) * a
        self._ema_speed += (math.hypot(pose.vx, pose.vy) - self._ema_speed) * a
        self._ema_lat += (abs(err.lateral_m) - self._ema_lat) * a
        settled = (
            err.fresh  # PX4 "target acquired" analogue: don't creep blind
            and self._ema_dist < 0.20
            and self._ema_speed < 0.12
            and self._ema_lat < 0.15  # NOSE near the corridor at handoff
        )
        self._settle_t = self._settle_t + dt if settled else 0.0
        # after 20 s, an imperfect attempt beats an abort-and-retry cycle
        if self._settle_t >= 0.4 or self._phase_t > 20.0:
            self._enter(DockPhase.FINAL_APPROACH)
        return cmd

    def _gate_hold(self, pose: Pose, hold_r_m: float, dt: float) -> ThrustCommand:
        """Hold the corridor while the cross-error window opens.

        NOT a go-around: the nose stays at grabbing distance inside the dock
        camera's cone, the draft estimator keeps learning, and the trim
        integrators keep working — so the commit that follows starts from a
        settled state instead of a lucky sample. Costs seconds; a retreat to
        the 1.5 m standoff costs an attempt and ~25 s.
        """
        return self._hover_axis(pose, hold_r_m + self.phys_cfg.nose_arm_m, dt)[0]

    def _release(self, pose: Pose, err: _AxisErrors,
                 capture: CaptureTelemetry) -> ThrustCommand:
        if capture.capture_switch:
            return ThrustCommand()  # remanence still holding — wait it out
        if err.range_m > 0.6:
            self._enter(DockPhase.DEPARTED)
            self._enter(DockPhase.FLYING)
            return ThrustCommand()
        cmd = self.nav.force_to_command(
            pose, 0.0, 0.0, 0.0, heading_des=self._approach_heading
        )
        cmd.forward_gf = -8.0  # back straight out of the mouth
        return cmd

