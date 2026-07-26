"""Base-station navigation primitives for an underactuated blimp.

The airframe has a forward pair (forward + yaw) and a vertical pair — no
side thrusters. Lateral motion therefore comes from pointing the nose where
force is needed; the primitive here turns a desired WORLD-frame force into
an honest ``ThrustCommand``:

- heading target = direction of the desired horizontal force,
- forward thrust = the component of that force along the CURRENT heading
  (reverse thrust allowed, at its weaker saturation),
- yaw = PD onto the heading target,
- vertical = the vertical force component,
- swing damper = the published "swing-reducer" pattern (research/04 §F):
  IMU pitch-rate feedback subtracted from forward thrust. The passive
  pendulum is underdamped on purpose; this is the active half.

Steady disturbances (HVAC drafts, buoyancy error) are handled by slow
per-axis integrators with hard clamps — the honest way to hold position
against a draft the same size as control authority (research/06 §G.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from meemoo.flight.constants import PhysicsConfig
from meemoo.flight.types import Pose, ThrustCommand, wrap_angle


@dataclass(slots=True)
class NavGains:
    """Tuned against the HONEST physics (never against loosened constants)."""

    kp_pos: float = 0.75  # 1/s: position error → desired velocity
    v_max_mps: float = 0.40  # cruise ceiling — floaty, not robotic
    kv: float = 1.6  # 1/s: velocity error → accel demand
    kp_z: float = 0.9
    kv_z: float = 1.8
    v_max_z_mps: float = 0.25
    ki_gf_per_ms: float = 0.55  # integrator rate, gf per metre-second
    integral_clamp_gf: float = 6.5  # drafts max ~4.5 gf steady per axis
    kp_yaw_gf: float = 7.0
    kd_yaw_gf: float = 6.0
    yaw_clamp_gf: float = 5.0
    swing_damp_gf: float = 55.0  # gf per rad/s of swing rate
    swing_damp_clamp_gf: float = 5.0
    heading_hold_deadband_n: float = 0.004  # below this force, keep heading
    heading_slew_rad_s: float = 2.0  # heading-target rate limit (anti-thrash)


@dataclass(slots=True)
class WorldNav:
    """Stateful force→command mapper with disturbance integrators."""

    cfg: PhysicsConfig
    gains: NavGains = field(default_factory=NavGains)
    ix: float = 0.0  # integrators, gram-force
    iy: float = 0.0
    iz: float = 0.0
    _hdg_des: float | None = None  # slew-limited heading target state
    _hold_hdg: float | None = None  # aim-then-hold hover heading
    _reaim_t: float = 0.0

    def reset_integrators(self) -> None:
        self.ix = self.iy = self.iz = 0.0

    def reset_hover(self) -> None:
        self._hold_hdg = None
        self._reaim_t = 0.0

    def integrate(
        self, ex: float, ey: float, ez: float, dt: float, *, gate_m: float = 0.8
    ) -> None:
        """Feed position error (m); accumulates clamped steady-force trim.

        Errors beyond ``gate_m`` don't integrate (anti-windup: the integrator
        exists for steady drafts near the target, not for the transit leg).
        """
        g = self.gains
        c = g.integral_clamp_gf
        if abs(ex) <= gate_m:
            self.ix = min(c, max(-c, self.ix + g.ki_gf_per_ms * ex * dt))
        if abs(ey) <= gate_m:
            self.iy = min(c, max(-c, self.iy + g.ki_gf_per_ms * ey * dt))
        if abs(ez) <= gate_m:
            self.iz = min(c, max(-c, self.iz + g.ki_gf_per_ms * ez * dt))

    # ----------------------------------------------------------- primitives
    def force_to_command(
        self,
        pose: Pose,
        fx_gf: float,
        fy_gf: float,
        fz_gf: float,
        *,
        heading_des: float | None = None,
        bidirectional: bool = False,
        prefer_heading: float | None = None,
        axis_heading: float | None = None,
        max_axis_dev_rad: float = 1.05,
        min_forward_gf: float | None = None,
        dt: float = 0.02,
    ) -> ThrustCommand:
        """Desired world force (gf) → honest thrust command.

        ``heading_des`` pins the nose; ``None`` lets it follow the force.
        ``bidirectional`` picks force direction OR its opposite — whichever
        pole is nearest ``prefer_heading`` (default: current heading) — and
        thrusts in reverse when pointed away; station-keeping NEEDS this
        (chasing every 180° force flip with the nose is a hover limit
        cycle). The follow-the-force target is slew-limited (noise on a
        small force vector must not thrash the yaw servo, which would
        starve forward authority through the shared-saturation cap), but a
        pole flip bypasses the slew: a thrust-sign change is not a turn.
        ``axis_heading`` clamps the crab angle to ``max_axis_dev_rad``.
        ``min_forward_gf`` floors forward thrust (funnel slide, §B.1).
        """
        g = self.gains
        fx_gf += self.ix
        fy_gf += self.iy
        fz_gf += self.iz
        f_h = math.hypot(fx_gf, fy_gf)
        if heading_des is None:
            if f_h * 9.80665e-3 <= g.heading_hold_deadband_n:
                heading_des = pose.heading_rad
            else:
                heading_des = math.atan2(fy_gf, fx_gf)
                if bidirectional:
                    ref = prefer_heading if prefer_heading is not None else pose.heading_rad
                    if abs(wrap_angle(heading_des - ref)) > math.pi / 2.0:
                        heading_des = wrap_angle(heading_des + math.pi)
            heading_des = self._slew(heading_des, bidirectional, dt)
            if axis_heading is not None:
                dev = wrap_angle(heading_des - axis_heading)
                dev = min(max_axis_dev_rad, max(-max_axis_dev_rad, dev))
                heading_des = wrap_angle(axis_heading + dev)
            self._hdg_des = heading_des
        else:
            self._hdg_des = heading_des
        yaw_err = wrap_angle(heading_des - pose.heading_rad)
        yaw_gf = g.kp_yaw_gf * yaw_err - g.kd_yaw_gf * pose.yaw_rate
        yaw_gf = min(g.yaw_clamp_gf, max(-g.yaw_clamp_gf, yaw_gf))
        return self._finish(pose, fx_gf, fy_gf, fz_gf, yaw_gf, min_forward_gf)

    def _slew(self, heading_des: float, bidirectional: bool, dt: float) -> float:
        """Rate-limit the follow-the-force heading target."""
        if self._hdg_des is None:
            return heading_des
        lim = self.gains.heading_slew_rad_s * dt
        step = wrap_angle(heading_des - self._hdg_des)
        if bidirectional:
            # undirected line: fold the step, then restore the raw pole
            if step > math.pi / 2.0:
                step -= math.pi
            elif step <= -math.pi / 2.0:
                step += math.pi
            line = wrap_angle(self._hdg_des + min(lim, max(-lim, step)))
            if abs(wrap_angle(heading_des - line)) <= math.pi / 2.0:
                return line
            return wrap_angle(line + math.pi)
        return wrap_angle(self._hdg_des + min(lim, max(-lim, step)))

    def _finish(
        self,
        pose: Pose,
        fx_gf: float,
        fy_gf: float,
        fz_gf: float,
        yaw_gf: float,
        min_forward_gf: float | None,
    ) -> ThrustCommand:
        g = self.gains

        # forward = force component along the CURRENT heading (crab honest)
        hx, hy = math.cos(pose.heading_rad), math.sin(pose.heading_rad)
        forward_gf = fx_gf * hx + fy_gf * hy
        # active swing damping (research/04 §F #3)
        damp = g.swing_damp_gf * pose.swing_rate
        damp = min(g.swing_damp_clamp_gf, max(-g.swing_damp_clamp_gf, damp))
        forward_gf -= damp
        # Yaw priority: the forward pair SHARES saturation with yaw
        # (mixer truth). Commanding both at once silently costs yaw — so cap
        # forward to leave the commanded yaw its per-motor headroom.
        # Attitude first, translation second.
        fwd_cap = 2.0 * max(0.0, self.cfg.thrust_max_gf_per_motor - abs(yaw_gf))
        rev_cap = 2.0 * max(0.0, self.cfg.thrust_reverse_gf_per_motor - abs(yaw_gf))
        forward_gf = min(fwd_cap, max(-rev_cap, forward_gf))
        if min_forward_gf is not None:
            forward_gf = max(min_forward_gf, forward_gf)
        return ThrustCommand(forward_gf=forward_gf, vertical_gf=fz_gf, yaw_gf=yaw_gf)

    def hover_command(
        self,
        pose: Pose,
        tx: float,
        ty: float,
        tz: float,
        dt: float,
        *,
        v_max: float = 0.25,
        prefer_heading: float | None = None,
    ) -> ThrustCommand:
        """Aim-then-hold station keeping.

        Continuously chasing the force vector with the nose ORBITS the
        target (heading lag vs. the rotating error direction = a sustained
        circling limit cycle — observed, not theorized). Instead: freeze the
        heading, thrust only along the body axis (reverse allowed), and
        RE-AIM discretely when the perpendicular force demand persists.
        Bounded hunting, no orbit. ``prefer_heading`` biases the re-aim pole
        (ALIGN wants the nose roughly on the dock axis).
        """
        g = self.gains
        fx, fy, fz = self.goto_force(pose, tx, ty, tz, dt, v_max=v_max)
        fx += self.ix
        fy += self.iy
        fz += self.iz
        if self._hold_hdg is None:
            self._hold_hdg = pose.heading_rad
        hx, hy = math.cos(self._hold_hdg), math.sin(self._hold_hdg)
        along = fx * hx + fy * hy
        perp = -fx * hy + fy * hx
        needs_reaim = (abs(perp) > 2.5 and abs(perp) > abs(along)) or along < -8.0
        self._reaim_t = self._reaim_t + dt if needs_reaim else 0.0
        if self._reaim_t > 1.0:
            raw = math.atan2(fy, fx)
            ref = prefer_heading if prefer_heading is not None else pose.heading_rad
            if abs(wrap_angle(raw - ref)) > math.pi / 2.0:
                raw = wrap_angle(raw + math.pi)  # nearer pole: reverse, don't turn
            self._hold_hdg = raw
            self._reaim_t = 0.0
            hx, hy = math.cos(self._hold_hdg), math.sin(self._hold_hdg)
            along = fx * hx + fy * hy
        yaw_err = wrap_angle(self._hold_hdg - pose.heading_rad)
        yaw_gf = g.kp_yaw_gf * yaw_err - g.kd_yaw_gf * pose.yaw_rate
        yaw_gf = min(g.yaw_clamp_gf, max(-g.yaw_clamp_gf, yaw_gf))
        cx, cy = math.cos(pose.heading_rad), math.sin(pose.heading_rad)
        return self._finish(pose, along * cx, along * cy, fz, yaw_gf, None)

    def steer_command(
        self,
        pose: Pose,
        forward_gf: float,
        fz_gf: float,
        heading_des: float,
        *,
        min_forward_gf: float | None = None,
    ) -> ThrustCommand:
        """Path-following primitive: explicit heading + explicit forward.

        While moving, lateral error is best regulated by STEERING (heading
        deviation redirects the velocity vector) — force-vector following
        only works when hovering. The vertical integrator still applies.
        """
        g = self.gains
        self._hdg_des = heading_des
        yaw_err = wrap_angle(heading_des - pose.heading_rad)
        yaw_gf = g.kp_yaw_gf * yaw_err - g.kd_yaw_gf * pose.yaw_rate
        yaw_gf = min(g.yaw_clamp_gf, max(-g.yaw_clamp_gf, yaw_gf))
        hx, hy = math.cos(pose.heading_rad), math.sin(pose.heading_rad)
        return self._finish(
            pose, forward_gf * hx, forward_gf * hy, fz_gf + self.iz, yaw_gf, min_forward_gf
        )

    def goto_force(
        self,
        pose: Pose,
        tx: float,
        ty: float,
        tz: float,
        dt: float,
        *,
        v_max: float | None = None,
    ) -> tuple[float, float, float]:
        """PD-with-integrator force (gf) toward a world point, velocity-shaped."""
        g = self.gains
        m = self.cfg.effective_mass_kg
        ex, ey, ez = tx - pose.x, ty - pose.y, tz - pose.z
        self.integrate(ex, ey, ez, dt)
        vmax = v_max if v_max is not None else g.v_max_mps
        dist = math.hypot(ex, ey)
        if dist > 1e-6:
            v_des = min(vmax, g.kp_pos * dist)
            vdx, vdy = v_des * ex / dist, v_des * ey / dist
        else:
            vdx = vdy = 0.0
        vdz = min(g.v_max_z_mps, max(-g.v_max_z_mps, g.kp_z * ez))
        to_gf = m / 9.80665e-3  # accel (m/s²) → gram-force
        fx = g.kv * (vdx - pose.vx) * to_gf
        fy = g.kv * (vdy - pose.vy) * to_gf
        fz = g.kv_z * (vdz - pose.vz) * to_gf
        return fx, fy, fz

    def arrived(self, pose: Pose, tx: float, ty: float, tz: float,
                *, pos_tol_m: float = 0.25, speed_tol_mps: float = 0.15) -> bool:
        close = math.hypot(tx - pose.x, ty - pose.y) < pos_tol_m and abs(tz - pose.z) < 0.25
        slow = math.hypot(pose.vx, pose.vy) < speed_tol_mps
        return close and slow
