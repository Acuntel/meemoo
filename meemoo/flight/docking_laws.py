"""Control laws for the docking state machine (mixin for DockingController).

The machine (phases, retries, timeouts) lives in docking.py; the geometry
and control laws — hover/align, pure pursuit of the mouth, capture hold,
release, recovery — live here. Everything is measured-against-honest-physics;
comments record the measured failure modes that shaped each law.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from meemoo.flight.types import (
    CaptureTelemetry,
    DockPhase,
    Pose,
    RelativePose,
    ThrustCommand,
    wrap_angle,
)

if TYPE_CHECKING:
    from meemoo.flight.constants import DockConfig, PhysicsConfig
    from meemoo.flight.docking import _AxisErrors
    from meemoo.flight.floorplan import DockPose
    from meemoo.flight.nav import WorldNav

_TRACKING_STALE_MS = 400.0  # PLD_BTOUT analogue


class ApproachLaws:
    """Mixin: control-law methods. State lives on DockingController."""

    if TYPE_CHECKING:  # attributes provided by DockingController
        nav: WorldNav
        phys_cfg: PhysicsConfig
        dock_cfg: DockConfig
        dock_pose: DockPose
        _axis: tuple[float, float]
        _axis_angle: float
        _approach_heading: float
        _settle_t: float
        _steer_i: float
        _ema_dist: float
        _ema_speed: float
        _ema_lat: float
        _ema_pm: float
        _stale_t: float
        _buoy_ff_gf: float
        _phase_t: float
        _hold_pt: tuple[float, float] | None

        def _enter(self, phase: DockPhase) -> None: ...
        def _standoff3(self) -> tuple[float, float, float]: ...

    # ---------------------------------------------------------------- laws
    def _goto_standoff(self, pose: Pose, dt: float) -> ThrustCommand:
        sx, sy, sz = self._standoff3()
        far = math.hypot(sx - pose.x, sy - pose.y) > 0.5
        f = self.nav.goto_force(pose, sx, sy, sz, dt)
        # long legs fly nose-first; near the point, thrust both ways (hover)
        return self.nav.force_to_command(pose, *f, bidirectional=not far, dt=dt)

    def _align(self, pose: Pose, err: _AxisErrors, dt: float) -> ThrustCommand:
        # Heading is NOT forced onto the axis: an underactuated blimp cannot
        # hold position against a lateral draft with its nose pinned — the
        # sphere's capture test never requires yaw. Instead the hover
        # TARGET is offset so that the NOSE (what the camera tracks and the
        # funnel judges) sits on the axis for whatever heading the draft
        # demands: center_lateral = −arm·sin(heading−axis).
        sx, sy, sz = self._standoff3()
        ax, ay = self._axis
        nose_lat = self.phys_cfg.nose_arm_m * math.sin(
            pose.heading_rad - self._axis_angle
        )
        tx = sx + ay * nose_lat  # −l_hat · nose_lat, l_hat = (−ay, ax)
        ty = sy - ax * nose_lat
        f = self.nav.goto_force(pose, tx, ty, sz, dt, v_max=0.25)
        cmd = self.nav.force_to_command(
            pose, *f, bidirectional=True, prefer_heading=self._approach_heading, dt=dt
        )
        a = min(1.0, dt / 0.3)  # ~0.3 s EMA smooths the σ-5 cm pose noise
        d3 = math.hypot(tx - pose.x, ty - pose.y) + max(0.0, abs(sz - pose.z) - 0.10)
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

    def _approach(self, pose: Pose, err: _AxisErrors, dt: float) -> ThrustCommand:
        # stale camera close-in = the classic crash — but give dead
        # reckoning a short grace before going around (tracking flickers)
        self._stale_t = 0.0 if err.fresh else self._stale_t + dt
        if self._stale_t > 0.7 and err.range_m > 0.25:
            self._enter(DockPhase.ABORT)
            return ThrustCommand()
        # predicted miss at the mouth plane if current drift holds — the
        # abort currency of a homing approach (nose radial at crossing is
        # what the funnel judges, NOT corridor adherence). Capped lookahead
        # + EMA: raw v_lat·(r/v) multiplies noise by seconds of lookahead.
        t_look = min(err.range_m / max(err.v_axis_mps, 0.05), 3.0)
        pm = err.lateral_m + err.v_lat_mps * t_look
        self._ema_pm += (pm - self._ema_pm) * min(1.0, dt / 0.25)
        if abs(self._ema_pm) > 0.5 and err.range_m < 0.7:
            self._enter(DockPhase.ABORT)  # hopeless line — go around
            return ThrustCommand()
        # Mouth gate: only abort when the NOSE is genuinely off AND drifting
        # to a miss on a short lookahead. A ballistic extrapolation reads a
        # healthy damped convergence (l crossing zero with velocity) as an
        # overshoot — that killed good approaches at the last moment.
        pm_short = err.lateral_m + err.v_lat_mps * min(t_look, 0.8)
        if err.range_m < 0.30 and abs(err.lateral_m) > 0.05 and abs(pm_short) > 0.11:
            self._enter(DockPhase.ABORT)  # would miss the mouth
            return ThrustCommand()
        if err.range_m < 0.12:
            self._enter(DockPhase.CAPTURE_PENDING)
        # Slow always-positive profile, tuned around the EQUILIBRIUM truth:
        # with near-zero drag the actual speed settles at
        # v_des + ff/(kv·m/g); any faster and the thrust floor turns the
        # final metre into an unsteerable ballistic coast that ends in an
        # over-speed bounce (measured — this, not the drafts, was the
        # dominant calm-air failure). Keep the equilibrium under
        # v_max_capture and steering stays live all the way to the mouth.
        v_des = min(0.16, max(0.09, 0.10 + 0.10 * (err.range_m - 0.35)))
        return self._path_follow(pose, err, v_des, dt)

    def _path_follow(
        self,
        pose: Pose,
        err: _AxisErrors,
        v_des: float,
        dt: float,
        *,
        min_forward_gf: float | None = None,
    ) -> ThrustCommand:
        """Pure pursuit of the MOUTH POINT (the PX4 home-on-beacon shape).

        The funnel judges nose radial error AT the mouth plane, never
        corridor adherence — so instead of fighting the underactuated
        airframe onto a straight rail, home the nose on the throat along a
        converging beam. Lateral drift is damped by leading the
        line-of-sight; the steering integrator learns the crab a steady
        draft demands."""
        m = self.phys_cfg.effective_mass_kg
        to_gf = m / 9.80665e-3
        g = self.nav.gains
        ax, ay = self._axis
        r = max(err.range_m, 0.02)
        led = err.lateral_m
        # nose→throat LOS in world frame (basis: axis out + l_hat)
        dx = -r * ax + led * ay
        dy = -r * ay - led * ax
        los = math.atan2(dy, dx)
        # PI on the lateral ERROR (integrating v_lat instead was a bug that
        # built a wrong-way heading bias and parked every approach at an
        # off-beam equilibrium — the calm-air killer)
        self._steer_i += 1.2 * err.lateral_m * dt
        self._steer_i = min(0.6, max(-0.6, self._steer_i))
        # lead cap shrinks with range: an unbounded crab lead swings the
        # 0.3 m nose arm out of the dock camera's FOV cone close-in
        lead_max = min(0.9, max(0.25, 1.4 * r))
        lead = min(lead_max, max(-lead_max, 5.0 * err.v_lat_mps + self._steer_i))
        # ALIGNMENT GATE: accelerating while the nose is off the LOS just
        # buys velocity in the wrong direction (the heading loop needs
        # ~2 s; the beam is crossed in ~4). While misaligned, ANCHOR — a
        # bare pirouette lets the draft rebuild the very offset being
        # turned toward — station-keep on the anchor point with along-axis
        # thrust and yaw onto the LOS; fly the beam once aligned.
        a_err = abs(wrap_angle(pose.heading_rad - los))
        align = math.cos(min(a_err, math.pi / 2.0))
        if align < 0.6 and err.range_m > 0.45:
            if self._hold_pt is None:
                self._hold_pt = (pose.x, pose.y)
            hpx, hpy = self._hold_pt
            hfx, hfy, hfz = self.nav.goto_force(pose, hpx, hpy, self.dock_pose.z, dt,
                                                v_max=0.2)
            hfx += self.nav.ix
            hfy += self.nav.iy
            ch, sh = math.cos(pose.heading_rad), math.sin(pose.heading_rad)
            along = hfx * ch + hfy * sh
            return self.nav.steer_command(
                pose, along, hfz - self._buoy_ff_gf, los,
                min_forward_gf=min_forward_gf,
            )
        self._hold_pt = None
        # feedforward shrinks with range so the speed equilibrium it sets
        # dies away before the mouth (see the profile note in _approach)
        ff = min(5.0, 2.0 + 10.0 * abs(err.lateral_m)) * max(0.3, align)
        ff *= min(1.0, max(0.25, err.range_m))
        forward_gf = g.kv * (v_des * max(0.15, align) - err.v_axis_mps) * to_gf + ff
        # always-positive thrust: reverse braking poisons lateral steering
        # (the lateral force of a heading tilt flips sign with the thrust)
        forward_gf = min(12.0, max(0.2 * align, forward_gf))
        heading_des = los + lead
        fz = (-2.5 * err.vertical_m - 2.2 * pose.vz) * to_gf - self._buoy_ff_gf
        self.nav.integrate(0.0, 0.0, -err.vertical_m, dt)
        return self.nav.steer_command(
            pose, forward_gf, fz, heading_des, min_forward_gf=min_forward_gf
        )

    def _capture_pending(
        self, pose: Pose, err: _AxisErrors, capture: CaptureTelemetry, dt: float
    ) -> ThrustCommand:
        if capture.confirmed:
            self._enter(DockPhase.CAPTURED)
            return ThrustCommand()
        if err.range_m > 0.35 or err.v_axis_mps < -0.10:
            self._enter(DockPhase.ABORT)  # bounced off the cone
            return ThrustCommand()
        if err.range_m < -0.2 and abs(err.lateral_m) > 0.15:
            self._enter(DockPhase.ABORT)  # went past BESIDE the dock — go around
            return ThrustCommand()
        to_gf = self.phys_cfg.effective_mass_kg / 9.80665e-3
        hold_gf = max(6.0, self.dock_cfg.min_slide_thrust_gf + 2.0)
        in_contact = (not err.fresh and err.range_m < 0.05) or err.range_m < 0.01
        if in_contact:
            # Nose is AT/INSIDE the mouth: freeze attitude (a yaw jump would
            # swing the 0.3 m nose arm off-axis right at the throat) and
            # hold the slide thrust — dropping below min_slide stalls +
            # backs out (research/06 §B.1). The cone wall centres us now.
            fz = (-2.0 * err.vertical_m - 2.0 * pose.vz) * to_gf - self._buoy_ff_gf
            return self.nav.force_to_command(
                pose, 0.0, 0.0, fz,
                heading_des=pose.heading_rad, min_forward_gf=hold_gf, dt=dt,
            )
        # Last free-flight centimetres: NO hold floor yet — thrust-flooring
        # before contact slams the nose past v_max_capture and bounces.
        # Keep homing gently down to contact speed.
        return self._path_follow(pose, err, 0.07, dt)

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

    def _errors(self, pose: Pose, relpose: RelativePose) -> _AxisErrors:
        from meemoo.flight.docking import _AxisErrors as AE

        fresh = relpose.tracking_valid and relpose.tracking_age_ms < _TRACKING_STALE_MS
        ax, ay = self._axis
        # NOSE lateral velocity: the camera tracks the nose, so the rate must
        # include the yaw-arm coupling (d/dt of arm·sin(heading−axis))
        vl = (
            -pose.vx * ay
            + pose.vy * ax
            + self.phys_cfg.nose_arm_m
            * math.cos(pose.heading_rad - self._axis_angle)
            * pose.yaw_rate
        )
        v_axis = -(pose.vx * ax + pose.vy * ay)
        if fresh:
            return AE(
                range_m=relpose.range_to_throat_mm / 1000.0,
                lateral_m=relpose.lateral_error_mm / 1000.0,
                vertical_m=relpose.vertical_error_mm / 1000.0,
                v_axis_mps=v_axis, v_lat_mps=vl, fresh=True,
            )
        # fallback: nose geometry from the coarse room pose (σ 5 cm)
        arm = self.phys_cfg.nose_arm_m
        nx = pose.x + arm * math.cos(pose.heading_rad)
        ny = pose.y + arm * math.sin(pose.heading_rad)
        nz = pose.z + arm * math.sin(pose.swing_rad)
        dx, dy = nx - self.dock_pose.x, ny - self.dock_pose.y
        return AE(
            range_m=dx * ax + dy * ay,
            lateral_m=-dx * ay + dy * ax,
            vertical_m=nz - self.dock_pose.z,
            v_axis_mps=v_axis, v_lat_mps=vl, fresh=False,
        )
