"""The honest 2.5D airframe physics (Constitution Art. II §4).

Models ALL FIVE must-haves from research/06 §G:
1. added mass ≈ displaced air (doubles inertia — the blimp coasts),
2. net buoyancy as a slowly drifting ±5 gf parameter randomized per episode,
3. per-motor thrust saturation at ~10 gf with an honest differential mixer,
4. funnel capture handled by :class:`~meemoo.flight.sim_dock.SimulatedDock`
   (this module feeds it nose pose + velocity each step),
5. low-frequency HVAC draft force fields of a few gf (OU wander + vents).

Plus the research/04 §F pendulum swing (underdamped, thrust-coupled) and a
~100 ms base-station→aircraft command latency queue. State is (x, y) on the
floor plan plus altitude z — "2D top-down" for the UI, but buoyancy and the
funnel need the vertical axis to stay honest.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from meemoo.flight.constants import GF_TO_N, PhysicsConfig
from meemoo.flight.floorplan import FloorPlan
from meemoo.flight.types import Pose, ThrustCommand, wrap_angle


@dataclass(slots=True)
class _Delayed:
    apply_at: float
    cmd: ThrustCommand


@dataclass(slots=True)
class AppliedThrust:
    """What the motors actually produced after the honest mixer."""

    forward_n: float = 0.0
    vertical_n: float = 0.0
    yaw_torque_nm: float = 0.0
    vertical_gf: float = 0.0
    forward_gf: float = 0.0


class BlimpPhysics:
    """Truthful airframe integrator. No controller logic lives here."""

    def __init__(
        self,
        config: PhysicsConfig,
        plan: FloorPlan,
        *,
        seed: int = 0,
        buoyancy_gf: float | None = None,
        drafts_enabled: bool = True,
    ) -> None:
        self.cfg = config
        self.plan = plan
        self.rng = random.Random(seed)
        self.t = 0.0
        # pose/velocity
        self.x, self.y = plan.standoff(1.0)
        self.z = 0.9
        self.heading = 0.0
        self.vx = self.vy = self.vz = 0.0
        self.yaw_rate = 0.0
        # pendulum swing
        self.swing = 0.0
        self.swing_rate = 0.0
        # buoyancy: per-episode value, slowly drifting, clamped
        self.buoyancy_gf = (
            buoyancy_gf if buoyancy_gf is not None else config.trim_default_gf
        )
        self._buoyancy_extra_gf = 0.0  # helium-loss coupling (sim_dock adjusts)
        # drafts: OU state + per-episode steady bias
        self._drafts_enabled = drafts_enabled
        self._draft = [0.0, 0.0, 0.0]
        b = config.draft_bias_max_gf
        self._draft_bias = (
            (self.rng.uniform(-b, b), self.rng.uniform(-b, b)) if drafts_enabled else (0.0, 0.0)
        )
        # battery
        self.battery_pct = 100.0
        self.motors_on = True
        # command latency
        self._queue: list[_Delayed] = []
        self._active = ThrustCommand()
        self.applied = AppliedThrust()
        # telemetry: low-pass hover duty → netBuoyancy_gf estimate
        self._hover_duty_lp = 0.0
        self._steady: tuple[float, float] = (0.0, 0.0)
        self.frozen = False  # captured on dock: dock holds the airframe

    # ------------------------------------------------------------- commands
    def command(self, cmd: ThrustCommand) -> None:
        """Queue a base-station command; applies after the radio latency."""
        self._queue.append(
            _Delayed(self.t + self.cfg.command_latency_s, ThrustCommand(
                cmd.forward_gf, cmd.vertical_gf, cmd.yaw_gf))
        )

    def _mature_commands(self) -> None:
        while self._queue and self._queue[0].apply_at <= self.t:
            self._active = self._queue.pop(0).cmd

    # ---------------------------------------------------------------- mixer
    def _mix(self, cmd: ThrustCommand) -> AppliedThrust:
        """Per-motor saturation. Forward pair shares forward + yaw authority."""
        cfg = self.cfg
        fwd_max = cfg.thrust_max_gf_per_motor
        rev_max = cfg.thrust_reverse_gf_per_motor
        # forward pair: left/right each in [-rev_max, +fwd_max]
        left = cmd.forward_gf / 2.0 - cmd.yaw_gf
        right = cmd.forward_gf / 2.0 + cmd.yaw_gf
        left = min(fwd_max, max(-rev_max, left))
        right = min(fwd_max, max(-rev_max, right))
        forward_gf = left + right
        yaw_diff_gf = right - left
        # vertical pair: each motor in [-rev_max, +fwd_max], "up" positive
        per = cmd.vertical_gf / 2.0
        per = min(fwd_max, max(-rev_max, per))
        vertical_gf = per * 2.0
        return AppliedThrust(
            forward_n=forward_gf * GF_TO_N,
            vertical_n=vertical_gf * GF_TO_N,
            yaw_torque_nm=yaw_diff_gf * GF_TO_N * cfg.yaw_lever_m,
            vertical_gf=vertical_gf,
            forward_gf=forward_gf,
        )

    # ------------------------------------------------------------- stepping
    def step(self, dt: float) -> None:
        cfg = self.cfg
        self.t += dt
        self._mature_commands()
        self._update_buoyancy(dt)
        self._update_draft(dt)

        if self.frozen:
            # Retention holds the airframe; motors idle, no drift.
            self.vx = self.vy = self.vz = 0.0
            self.yaw_rate = 0.0
            self.swing *= max(0.0, 1.0 - 2.0 * dt)
            self.swing_rate = 0.0
            self.applied = AppliedThrust()
            return

        ap = self._mix(self._active) if self.motors_on else AppliedThrust()
        self.applied = ap
        m = cfg.effective_mass_kg

        # thrust in world frame; pendulum swing tilts the thrust vector
        tilt = math.cos(self.swing)
        fx = ap.forward_n * tilt * math.cos(self.heading)
        fy = ap.forward_n * tilt * math.sin(self.heading)
        fz = ap.vertical_n + ap.forward_n * math.sin(self.swing)

        # buoyancy (positive = light = up) and drafts
        fz += (self.buoyancy_gf + self._buoyancy_extra_gf) * GF_TO_N
        fx += self._draft[0] * GF_TO_N
        fy += self._draft[1] * GF_TO_N
        fz += self._draft[2] * GF_TO_N

        # drag: quadratic + linear
        speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        drag = cfg.drag_quad_n_per_mps2 * speed + cfg.drag_lin_n_per_mps
        fx -= drag * self.vx
        fy -= drag * self.vy
        fz -= drag * self.vz

        ax, ay, az = fx / m, fy / m, fz / m
        self.vx += ax * dt
        self.vy += ay * dt
        self.vz += az * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self._clamp_walls()

        # yaw dynamics
        torque = ap.yaw_torque_nm - cfg.yaw_drag_nms * self.yaw_rate
        self.yaw_rate += (torque / cfg.yaw_inertia_kg_m2) * dt
        self.heading = wrap_angle(self.heading + self.yaw_rate * dt)

        # pendulum swing driven by along-heading acceleration
        a_along = ax * math.cos(self.heading) + ay * math.sin(self.heading)
        w0 = cfg.swing_omega0
        self.swing_rate += (
            -(w0**2) * self.swing
            - 2.0 * cfg.swing_zeta_passive * w0 * self.swing_rate
            + a_along / cfg.swing_arm_m
        ) * dt
        self.swing += self.swing_rate * dt

        # battery: drains while flying, faster when working hard
        duty = (abs(ap.forward_gf) + abs(ap.vertical_gf)) / (
            2.0 * cfg.thrust_max_gf_per_motor * 2.0
        )
        if self.motors_on and self.z > 0.05:
            rate = (0.5 + 0.5 * min(1.0, duty)) * (100.0 / cfg.battery_flight_s)
            self.battery_pct = max(0.0, self.battery_pct - rate * dt)

        # hover-duty low-pass → netBuoyancy estimate (research/06 §G telemetry)
        vert_duty = ap.vertical_gf / (2.0 * cfg.thrust_max_gf_per_motor)
        self._hover_duty_lp += (vert_duty - self._hover_duty_lp) * min(1.0, dt / 3.0)

    def _update_buoyancy(self, dt: float) -> None:
        cfg = self.cfg
        self.buoyancy_gf += self.rng.gauss(0.0, cfg.buoyancy_drift_sigma_gf) * math.sqrt(dt)
        clamp = cfg.buoyancy_clamp_gf
        self.buoyancy_gf = min(clamp, max(-clamp, self.buoyancy_gf))

    def _update_draft(self, dt: float) -> None:
        if not self._drafts_enabled:
            return
        cfg = self.cfg
        amp = cfg.draft_amp_gf
        sig = cfg.draft_sigma_gf * math.sqrt(dt)
        for i in range(3):
            frac = cfg.draft_vertical_frac if i == 2 else 1.0
            v = self._draft[i]
            v += (-v / cfg.draft_tau_s) * dt + self.rng.gauss(0.0, sig * frac)
            self._draft[i] = min(amp * frac, max(-amp * frac, v))
        # steady per-episode bias + vent fields
        vent_x = self._draft_bias[0]
        vent_y = self._draft_bias[1]
        for vent in self.plan.vents:
            d = math.hypot(self.x - vent.x, self.y - vent.y)
            if d < vent.radius_m:
                falloff = 1.0 - d / vent.radius_m
                vent_x += math.cos(vent.dir_rad) * vent.force_gf * falloff
                vent_y += math.sin(vent.dir_rad) * vent.force_gf * falloff
        self._steady = (vent_x, vent_y)

    @property
    def draft_gf(self) -> tuple[float, float, float]:
        return (
            self._draft[0] + self._steady[0],
            self._draft[1] + self._steady[1],
            self._draft[2],
        )

    def _clamp_walls(self) -> None:
        x0, y0, x1, y1 = self.plan.bounds
        pad = self.cfg.diameter_m / 2.0
        if self.x < x0 + pad:
            self.x, self.vx = x0 + pad, max(0.0, self.vx)
        elif self.x > x1 - pad:
            self.x, self.vx = x1 - pad, min(0.0, self.vx)
        if self.y < y0 + pad:
            self.y, self.vy = y0 + pad, max(0.0, self.vy)
        elif self.y > y1 - pad:
            self.y, self.vy = y1 - pad, min(0.0, self.vy)
        if self.z < 0.0:
            self.z, self.vz = 0.0, max(0.0, self.vz)
        elif self.z > self.cfg.ceiling_m:
            self.z, self.vz = self.cfg.ceiling_m, min(0.0, self.vz)

    # ------------------------------------------------------------ telemetry
    @property
    def net_buoyancy_true_gf(self) -> float:
        return self.buoyancy_gf + self._buoyancy_extra_gf

    @property
    def net_buoyancy_est_gf(self) -> float:
        """Derived exactly as the real dock will: hover thrust duty inverted."""
        return -self._hover_duty_lp * 2.0 * self.cfg.thrust_max_gf_per_motor

    def nose_position(self) -> tuple[float, float, float]:
        """The capture-cone contact point; swing moves it vertically."""
        arm = self.cfg.nose_arm_m
        return (
            self.x + arm * math.cos(self.heading),
            self.y + arm * math.sin(self.heading),
            self.z + arm * math.sin(self.swing),
        )

    def pose(self, noise_m: float = 0.0, rng: random.Random | None = None) -> Pose:
        """Coarse room-tracking pose (base-station camera, σ ~5 cm)."""
        r = rng or self.rng

        def n() -> float:
            return r.gauss(0.0, noise_m) if noise_m > 0 else 0.0

        return Pose(
            x=self.x + n(), y=self.y + n(), z=self.z + n(),
            heading_rad=self.heading, vx=self.vx, vy=self.vy, vz=self.vz,
            yaw_rate=self.yaw_rate, swing_rad=self.swing,
            swing_rate=self.swing_rate, t=self.t,
        )
