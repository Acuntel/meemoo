"""Honest-physics constants for the 2D sim (Constitution Art. II §4).

THE SIMULATOR TELLS THE TRUTH. Every number here traces to the research
docs; a controller that only works with generous physics is a bug. NEVER
loosen these to make a controller pass — tests/flight/test_physics.py pins
them and will fail loudly if someone tries.

Sources:
- research/04 §A: 120 L sphere, 0.61 m diameter, 65 g payload, ~50 g BOM.
- research/06 (CERN blimp): thrust saturation ±0.1 N ≈ 10 gf per motor.
- research/06 §G: added mass ≈ displaced air mass (~doubles inertia);
  buoyancy ±5 gf drifting per episode; funnel capture (R_capture, v_max);
  HVAC drafts of a few gf — the same magnitude as control authority.
- research/04 §F: pendulum swing, natural period stretched to 1.5–3 s by
  added mass; passive fin damping; active "swing-reducer" rate feedback.
- CONSTITUTION Art. I §2: trimmed 2–4 g NEGATIVELY buoyant by default.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

GF_TO_N = 9.80665e-3  # 1 gram-force in newtons
AIR_DENSITY_G_PER_L = 1.204  # 20 °C sea level (research/04 §A)


@dataclass(frozen=True, slots=True)
class PhysicsConfig:
    """Airframe + environment truth. Defaults are the v1 target vehicle."""

    # --- airframe (research/04 §A) ---
    volume_l: float = 120.0
    diameter_m: float = 0.61
    vehicle_mass_kg: float = 0.125  # 65 g payload + ~40 g envelope + ~20 g helium
    # Added mass ≈ displaced air mass (research/06 §G.1) — doubles inertia.
    added_mass_kg: float = 120.0 * AIR_DENSITY_G_PER_L / 1000.0  # 0.1445 kg

    # --- thrust (CERN measurement: ±0.1 N per coreless motor) ---
    thrust_max_gf_per_motor: float = 10.0
    thrust_reverse_gf_per_motor: float = 5.0  # reversed props ≈ half efficiency
    n_forward_motors: int = 2  # differential pair: forward + yaw share saturation
    n_vertical_motors: int = 2
    yaw_lever_m: float = 0.15
    yaw_inertia_kg_m2: float = 0.0095  # ~2/5·m_eff·r² for the sphere
    yaw_drag_nms: float = 0.004

    # --- drag: quadratic (sphere Cd 0.47) + linear (fins/viscous) ---
    drag_quad_n_per_mps2: float = 0.083  # ½·ρ·Cd·A for a 0.61 m sphere
    drag_lin_n_per_mps: float = 0.020

    # --- buoyancy (Art. I §2 + research/06 §G.2) ---
    trim_default_gf: float = -3.0  # NEGATIVE trim: power loss = gentle descent
    buoyancy_episode_range_gf: float = 5.0  # docking proven across ±5 gf, both signs
    buoyancy_drift_sigma_gf: float = 0.05  # slow random walk per √s
    buoyancy_clamp_gf: float = 5.0

    # --- HVAC drafts (research/06 §G.5): wandering few-gf force field ---
    draft_amp_gf: float = 3.0  # clamp — same scale as control authority
    draft_tau_s: float = 20.0  # OU time constant (low-frequency wander)
    draft_sigma_gf: float = 0.38  # → stationary std ≈ 1.2 gf per axis
    draft_bias_max_gf: float = 1.5  # per-episode steady flow component
    draft_vertical_frac: float = 0.3

    # --- pendulum swing (research/04 §F) ---
    swing_period_s: float = 2.2  # 0.78 s natural, stretched by added mass
    swing_zeta_passive: float = 0.06  # fins only — underdamped on purpose
    nose_arm_m: float = 0.30  # swing moves the nose: r·sin(θ) vs R_capture

    # --- battery (MASTER_PROMPT §5) ---
    battery_flight_s: float = 1200.0  # 20 min full → empty in flight
    battery_charge_s: float = 2400.0  # ~40 min 0 → full on dock (0.5C-ish)
    auto_return_pct: float = 25.0

    # --- world ---
    ceiling_m: float = 2.4
    command_latency_s: float = 0.10  # base-station → aircraft radio latency

    @property
    def effective_mass_kg(self) -> float:
        return self.vehicle_mass_kg + self.added_mass_kg

    @property
    def swing_omega0(self) -> float:
        return 2.0 * math.pi / self.swing_period_s

    @property
    def swing_arm_m(self) -> float:
        """Equivalent pendulum length from the (stretched) period."""
        return 9.80665 / (self.swing_omega0**2)


@dataclass(frozen=True, slots=True)
class DockConfig:
    """Funnel + magnet + charge truth (research/06 §B–§D, §G.4)."""

    # Funnel capture model: succeed iff radial error < r_capture AT contact
    # AND axial speed < v_max — else bounce off and abort.
    r_capture_m: float = 0.075  # 15–20 cm mouth → ±7.5 cm
    r_throat_m: float = 0.02
    v_max_capture_mps: float = 0.15
    throat_depth_m: float = 0.10
    # Held forward thrust substitutes for gravity (research/06 §B.1): below
    # this the nose stalls on the cone wall and can slide back out.
    min_slide_thrust_gf: float = 3.0
    slide_backout_rate: float = 0.02  # funnel-progress lost per second when stalled
    # Dock-side electromagnet: seats the last centimetre once close enough.
    magnet_seat_progress: float = 0.90  # retention can snap from here
    contact_progress: float = 0.85  # ring continuity closes here
    switch_progress: float = 0.995  # hall/reed switch = fully seated
    bounce_restitution: float = 0.3
    # Remanence after cutting current, without the reverse pulse (§B release)
    remanence_gf: float = 2.0
    # Dock camera (outward along the approach corridor, research/06 §A).
    # Wide-angle guidance lens (fisheye-class, 120° full FOV) — a DESIGN
    # choice of our dock hardware; the noise/rate stay honest.
    camera_rate_hz: float = 20.0
    camera_range_m: float = 4.5
    camera_fov_half_deg: float = 60.0
    noise_lateral_m: float = 0.005  # ~1 cm-class lateral precision
    noise_range_m: float = 0.020  # range is the weak axis
    # Helium (research/04 §E): ~0.3–0.6 g lift/day → level decays slowly
    helium_decay_pct_per_day: float = 0.5
    helium_gf_per_pct: float = 0.4  # lost level shows up as heavier trim
