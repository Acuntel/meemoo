"""Online HVAC-draft estimator — the blimp is its own anemometer.

research/06 §G.5 names the draft field the dominant indoor error source: a
low-frequency wandering force of a few gram-force, *the same magnitude as
control authority*. A reactive loop can only discover it by drifting off the
beam first, and on a three-second final approach the error is spent by then.
So estimate it explicitly and crab into it (``docking_laws._path_follow``
feeds it straight into the heading; ``dock_plan`` charges it against the
lateral authority budget when deciding whether to commit).

This is a deterministic disturbance observer — two states per axis, no
learning, no model, fully printable — so it can run on the base station and
be debugged from a log. The base station knows what it commanded, knows the
mixer that shaped it (physics._mix is vehicle spec, not a sim detail), knows
the ~100 ms radio delay before the command took effect, and knows the
effective mass. Whatever the measured velocity does that the commanded
thrust does not explain IS the ambient force:

    m·v̇ = F_thrust + F_draft − F_drag(v)

    v̂̇ = (F_thrust + d̂ − F_drag)/m + 2ω·(v − v̂)     (velocity predictor)
    d̂̇ = m·ω²·(v − v̂)                                (disturbance state)

Bandwidth is deliberately low (ω ≈ 0.9 rad/s ≈ 1.1 s): the draft wanders
with τ = 20 s, so anything faster is fitting pose noise. ``confidence``
ramps with settling time and collapses when the innovation stays large —
the feedforward is scaled by it, so a confused estimator does nothing
rather than something wrong.

Vertical: the netBuoyancy telemetry is fed in as a KNOWN input, so d̂_z is
the vertical draft plus whatever the buoyancy estimate got wrong — never a
second copy of buoyancy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from meemoo.flight.constants import GF_TO_N, PhysicsConfig
from meemoo.flight.types import Pose, ThrustCommand


@dataclass(frozen=True, slots=True)
class DraftEstimate:
    """Ambient force on the airframe, gram-force, world frame."""

    x_gf: float = 0.0
    y_gf: float = 0.0
    z_gf: float = 0.0
    confidence: float = 0.0  # 0 = ignore me, 1 = settled and consistent

    def lateral_gf(self, axis: tuple[float, float]) -> float:
        """Component along the dock's lateral unit vector l̂ = (−a_y, a_x)."""
        ax, ay = axis
        return -self.x_gf * ay + self.y_gf * ax


@dataclass(slots=True)
class _Delayed:
    apply_at: float
    cmd: ThrustCommand


class DraftEstimator:
    """Luenberger observer on (velocity, ambient force), per world axis."""

    def __init__(
        self,
        cfg: PhysicsConfig,
        *,
        omega: float = 0.9,
        clamp_gf: float = 6.0,
        settle_s: float = 4.0,
    ) -> None:
        self.cfg = cfg
        self.omega = omega
        self.clamp_gf = clamp_gf
        self.settle_s = settle_s
        self._queue: list[_Delayed] = []
        self._active = ThrustCommand()
        self._v = [0.0, 0.0, 0.0]
        self._d = [0.0, 0.0, 0.0]
        self._innov = 0.0
        self._elapsed = 0.0
        self._t: float | None = None
        self.estimate = DraftEstimate()

    def reset(self) -> None:
        """Forget the disturbance state (new episode / after a capture)."""
        self._v = [0.0, 0.0, 0.0]
        self._d = [0.0, 0.0, 0.0]
        self._innov = 0.0
        self._elapsed = 0.0
        self.estimate = DraftEstimate()

    # ------------------------------------------------------------- commands
    def record(self, cmd: ThrustCommand, t: float) -> None:
        """Log a command the base station just sent (it bites one radio
        latency from now — the observer must not credit it before then)."""
        self._queue.append(_Delayed(
            t + self.cfg.command_latency_s,
            ThrustCommand(cmd.forward_gf, cmd.vertical_gf, cmd.yaw_gf),
        ))
        if len(self._queue) > 200:  # a clock that never advances is a bug,
            del self._queue[0]      # not a reason to grow without bound

    def _mature(self, t: float) -> None:
        while self._queue and self._queue[0].apply_at <= t:
            self._active = self._queue.pop(0).cmd

    def _applied_gf(self) -> tuple[float, float]:
        """(forward, vertical) gf actually produced, per the honest mixer:
        the forward pair shares its saturation with yaw."""
        cfg = self.cfg
        fwd, rev = cfg.thrust_max_gf_per_motor, cfg.thrust_reverse_gf_per_motor
        c = self._active
        left = min(fwd, max(-rev, c.forward_gf / 2.0 - c.yaw_gf))
        right = min(fwd, max(-rev, c.forward_gf / 2.0 + c.yaw_gf))
        per = min(fwd, max(-rev, c.vertical_gf / 2.0))
        return left + right, 2.0 * per

    # --------------------------------------------------------------- update
    def update(
        self, pose: Pose, dt: float, *, buoyancy_gf: float = 0.0, learn: bool = True
    ) -> DraftEstimate:
        """One observer tick. ``learn=False`` freezes the disturbance state
        (constrained contact — a cone wall holding the nose still would
        otherwise read as a hurricane)."""
        self._mature(pose.t)
        if self._t is None:  # first tick: seed the predictor from the vehicle
            self._v = [pose.vx, pose.vy, pose.vz]
        self._t = pose.t
        cfg = self.cfg
        m = cfg.effective_mass_kg
        fwd_gf, vert_gf = self._applied_gf()
        thrust = (
            fwd_gf * math.cos(pose.heading_rad),
            fwd_gf * math.sin(pose.heading_rad),
            vert_gf + buoyancy_gf,
        )
        meas = (pose.vx, pose.vy, pose.vz)
        speed = math.sqrt(sum(v * v for v in meas))
        drag = cfg.drag_quad_n_per_mps2 * speed + cfg.drag_lin_n_per_mps
        innov = 0.0
        for i in range(3):
            e = meas[i] - self._v[i]
            f_n = (thrust[i] + self._d[i]) * GF_TO_N - drag * self._v[i]
            self._v[i] += (f_n / m + 2.0 * self.omega * e) * dt
            if learn:
                self._d[i] += (m * self.omega**2 * e / GF_TO_N) * dt
                self._d[i] = min(self.clamp_gf, max(-self.clamp_gf, self._d[i]))
            if i < 2:
                innov += e * e
        self._innov += (math.sqrt(innov) - self._innov) * min(1.0, dt / 0.5)
        self._elapsed += dt
        ramp = min(1.0, self._elapsed / self.settle_s)
        agree = max(0.0, 1.0 - self._innov / 0.12)
        self.estimate = DraftEstimate(
            self._d[0], self._d[1], self._d[2], ramp * agree
        )
        return self.estimate
