"""Rig constants + result records for the 3D cross-validation experiment.

No mujoco import here — this module is always importable (tests for the
mixer math and result classification run even without the physics3d group).

Geometry note (a real finding, see docs/PHYSICS_VALIDATION.md): the assigned
dock cone (40 cm mouth -> 12 cm throat over 35 cm) cannot be reached by the
bare 0.61 m sphere — the envelope seats on the mouth rim with its surface
only ~8.5 cm into a 35 cm cone. Reaching the throat magnet requires a nose
probe of ~0.585 m from sphere center (~0.28 m proud of the envelope). The
probe length is therefore derived from the cone, not chosen freely:
tip_reach = rim_seat_distance + cone_depth with a 5 mm rim clearance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

GF_TO_N = 9.80665e-3  # 1 gram-force in newtons
G = 9.80665


@dataclass(frozen=True, slots=True)
class Rig3DConfig:
    """Everything the MJCF builder + world need. SI units unless suffixed."""

    # --- air (engine-owned fluid model) ---
    air_density: float = 1.204  # kg/m^3 (research/04 SectionA)
    air_viscosity: float = 1.81e-5  # Pa*s
    # fluidcoef: blunt drag tuned to the measured sphere Cd 0.47; the rest
    # stay at MuJoCo defaults. Added mass comes from the engine's
    # potential-flow ellipsoid model (sphere: 0.5 * displaced air mass).
    fluidcoef: str = "0.47 0.25 1.5 1.7 1.0"

    # --- vehicle (v1 target: 120 L / 0.61 m sphere, 125 g all-up) ---
    envelope_radius: float = 0.305
    shell_mass: float = 0.058  # envelope + helium + structure, thin shell
    probe_mass: float = 0.002  # carbon docking boom
    gondola_mass: float = 0.065  # the 65 g payload point mass
    gondola_drop: float = 0.15  # hung 0.15 m below sphere center
    # probe: tip surface reach from sphere center (see geometry note above)
    tip_reach: float = 0.585
    tip_radius: float = 0.01

    # --- thrust (CERN ~10 gf per coreless motor; reverse ~half) ---
    thrust_fwd_max_gf: float = 10.0
    thrust_rev_max_gf: float = 5.0
    motor_y: float = 0.15  # forward pair lever arm (matches 2D yaw_lever_m)
    vmotor_x: float = 0.10  # vertical pair fore/aft placement
    max_speed_mps: float = 1.3  # A5 firmware governor

    # --- passive fin damping (research/04 SectionF: fins give zeta ~0.06;
    # a bare sphere in the fluid model has almost no rotational damping, so
    # the fins are the one hand constant kept — documented, not hidden) ---
    fin_rot_damping_nms: float = 0.0025  # pitch/roll
    yaw_drag_nms: float = 0.004  # same value as the 2D sim

    # --- dock cone (assignment spec: 40 cm mouth -> 12 cm throat over
    # 35 cm). Measured in this rig: the 12 cm throat leaves the probe tip up
    # to ~5 cm off the magnet axis — a proximity magnet (15 mm engage) can
    # NEVER trigger. So the last 6 cm of the same 35 cm depth is a second-
    # stage centering cup (12 cm -> 1.2 cm) that funnels the tip onto the
    # magnet. A design finding for the bench, not a controller fix. ---
    mouth_radius: float = 0.20  # 40 cm mouth
    throat_radius: float = 0.06  # 12 cm spec throat (start of the cup)
    cone_depth: float = 0.35  # mouth plane x=0 -> magnet plate x=-0.35
    cup_depth: float = 0.06  # centering cup inside the last 6 cm
    cup_exit_radius: float = 0.012  # snug around the 10 mm tip
    dock_z: float = 1.2
    n_panels: int = 16
    magnet_engage_m: float = 0.015  # electromagnet snap: weld under 15 mm
    seat_m: float = 0.002  # hall/reed "seated" switch threshold
    continuity_m: float = 0.004  # charge-ring contact threshold
    remanence_s: float = 0.5  # core remanence window after magnet-off

    # --- buoyancy (net, per-episode, both signs — 2D contract) ---
    buoyancy_range_gf: float = 5.0
    buoyancy_walk_sigma_gf: float = 0.05  # per sqrt(s), same as 2D
    buoyancy_clamp_gf: float = 5.0

    # --- HVAC drafts as WIND through the engine's fluid drag model.
    # OU-wandering wind velocity; 0.83 m/s on the 0.29 m^2 sphere is ~4.7 gf
    # of drag — the same few-gf scale as the 2D draft force field. ---
    wind_tau_s: float = 20.0
    wind_sigma: float = 0.104  # OU noise -> stationary std ~0.33 m/s per axis
    wind_axis_clamp: float = 0.60
    wind_vertical_frac: float = 0.3
    wind_bias_max: float = 0.30  # per-episode steady flow
    wind_speed_cap: float = 0.85

    # --- room ---
    room_x: tuple[float, float] = (-0.36, 4.6)  # wall behind the dock face
    room_y: tuple[float, float] = (-3.1, 3.1)
    ceiling: float = 2.4

    # --- timing ---
    timestep: float = 0.004
    command_latency_s: float = 0.10  # base-station -> aircraft radio latency

    @property
    def total_mass(self) -> float:
        return self.shell_mass + self.probe_mass + self.gondola_mass

    @property
    def rim_seat_x(self) -> float:
        """Sphere-center x where the envelope seats on the mouth rim."""
        return math.sqrt(self.envelope_radius**2 - self.mouth_radius**2)

    @property
    def seated_center_x(self) -> float:
        """Sphere-center x when the tip is at the throat (weld pose)."""
        return self.tip_reach - self.cone_depth


def mix_thrust(
    forward_gf: float, vertical_gf: float, yaw_gf: float, cfg: Rig3DConfig
) -> tuple[float, float, float, float]:
    """The 2D sim's honest mixer, per motor: (left, right, vleft, vright) gf.

    Forward pair shares forward + yaw authority and saturates per motor —
    identical math to meemoo.flight.physics.BlimpPhysics._mix.
    """
    fwd, rev = cfg.thrust_fwd_max_gf, cfg.thrust_rev_max_gf
    left = min(fwd, max(-rev, forward_gf / 2.0 - yaw_gf))
    right = min(fwd, max(-rev, forward_gf / 2.0 + yaw_gf))
    per = min(fwd, max(-rev, vertical_gf / 2.0))
    return (left, right, per, per)


@dataclass(slots=True)
class Episode3DResult:
    """One randomized 3D docking episode, same fields the 2D runner reports
    plus the 3D-only physics measurements."""

    seed: int
    ok: bool
    retries: int
    sim_time_s: float
    buoyancy_gf: float
    end_phase: str
    mouth_entries: int
    contact_speed_mps: float | None  # |v| at the mouth crossing that captured
    min_tip_throat_m: float
    aborts_from: dict[str, int] = field(default_factory=dict)

    @property
    def failure_mode(self) -> str:
        if self.ok:
            return "captured"
        if self.end_phase == "DOCK_FAILED":
            return "max_attempts"
        return f"timeout_{self.end_phase}"


@dataclass(slots=True)
class BumpResult:
    """One 1 N / 0.2 s shove during hover: pendulum recovery numbers."""

    seed: int
    damper: bool
    settle_s: float | None  # None = never settled inside the window
    max_tilt_deg: float


def success_rates(results: list[Episode3DResult]) -> dict[str, float]:
    n = max(1, len(results))
    first = sum(1 for r in results if r.ok and r.retries == 0)
    within1 = sum(1 for r in results if r.ok and r.retries <= 1)
    any_ok = sum(1 for r in results if r.ok)
    return {
        "episodes": float(len(results)),
        "first_attempt": first / n,
        "within_one_retry": within1 / n,
        "within_max_attempts": any_ok / n,
    }


def failure_histogram(results: list[Episode3DResult]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for r in results:
        hist[r.failure_mode] = hist.get(r.failure_mode, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: -kv[1]))
