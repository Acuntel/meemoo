"""Honest-physics pins + airframe behavior (Constitution Art. II §4).

The constants tests exist to fail LOUDLY if anyone loosens the physics to
make a controller pass — that is a bug by constitutional definition.
"""

from __future__ import annotations

import math

import pytest

from meemoo.flight.constants import AIR_DENSITY_G_PER_L, DockConfig, PhysicsConfig
from meemoo.flight.floorplan import load_plan
from meemoo.flight.physics import BlimpPhysics
from meemoo.flight.types import ThrustCommand


@pytest.fixture()
def phys() -> BlimpPhysics:
    p = BlimpPhysics(PhysicsConfig(), load_plan("apartment"), seed=1,
                     buoyancy_gf=-3.0, drafts_enabled=False)
    p.x, p.y, p.z = 4.0, 3.0, 1.2
    return p


class TestConstantsPinned:
    """research/04 §A + research/06 §G numbers — NEVER loosen these."""

    def test_airframe(self) -> None:
        cfg = PhysicsConfig()
        assert cfg.volume_l == 120.0
        assert cfg.diameter_m == 0.61
        # added mass ≈ displaced air mass — doubles effective inertia
        assert cfg.added_mass_kg == pytest.approx(120.0 * AIR_DENSITY_G_PER_L / 1000.0)
        assert cfg.effective_mass_kg >= 2.0 * cfg.added_mass_kg * 0.85

    def test_thrust_saturation_single_digit_grams(self) -> None:
        assert PhysicsConfig().thrust_max_gf_per_motor == 10.0

    def test_negative_trim_default(self) -> None:
        cfg = PhysicsConfig()
        assert -4.0 <= cfg.trim_default_gf <= -2.0  # Art. I §2 / IV §6

    def test_buoyancy_randomization_range(self) -> None:
        assert PhysicsConfig().buoyancy_episode_range_gf == 5.0

    def test_drafts_same_scale_as_authority(self) -> None:
        cfg = PhysicsConfig()
        assert cfg.draft_amp_gf >= 3.0  # a few gf — the control problem itself

    def test_battery_twenty_minutes(self) -> None:
        assert PhysicsConfig().battery_flight_s == 1200.0

    def test_funnel_capture_model(self) -> None:
        d = DockConfig()
        assert d.r_capture_m <= 0.08
        assert d.v_max_capture_mps <= 0.15
        assert d.min_slide_thrust_gf >= 3.0

    def test_command_latency(self) -> None:
        assert PhysicsConfig().command_latency_s == pytest.approx(0.10)


class TestAirframe:
    def test_added_mass_slows_acceleration(self, phys: BlimpPhysics) -> None:
        phys.command(ThrustCommand(forward_gf=10.0))
        for _ in range(50):  # 1 s
            phys.step(0.02)
        # F/m_eff with added mass ≈ 0.36 m/s²; without it would be ~0.78
        speed = math.hypot(phys.vx, phys.vy)
        assert 0.15 < speed < 0.45

    def test_thrust_saturates_at_mixer(self, phys: BlimpPhysics) -> None:
        phys.command(ThrustCommand(forward_gf=500.0))
        for _ in range(20):
            phys.step(0.02)
        assert phys.applied.forward_gf <= 2 * phys.cfg.thrust_max_gf_per_motor + 1e-9

    def test_forward_and_yaw_share_saturation(self, phys: BlimpPhysics) -> None:
        phys.command(ThrustCommand(forward_gf=20.0, yaw_gf=10.0))
        for _ in range(20):
            phys.step(0.02)
        # per-motor clamp at 10 gf: demanding yaw with full forward COSTS
        # forward (left motor rails at 0, right at 10) — never free
        assert phys.applied.forward_gf == pytest.approx(10.0)
        assert phys.applied.yaw_torque_nm > 0.0

    def test_command_latency_queue(self, phys: BlimpPhysics) -> None:
        phys.command(ThrustCommand(forward_gf=10.0))
        phys.step(0.05)  # < latency: not applied yet
        assert phys.applied.forward_gf == 0.0
        phys.step(0.06)  # past 100 ms
        assert phys.applied.forward_gf > 0.0

    def test_power_loss_is_gentle_descent(self, phys: BlimpPhysics) -> None:
        """Art. IV §6: negative trim ⇒ motors off means slow descent,
        never a ceiling-parked failure."""
        phys.motors_on = False
        z0 = phys.z
        for _ in range(int(30.0 / 0.02)):
            phys.step(0.02)
        assert phys.z < z0  # it came down
        assert phys.z < 0.2  # settled at the floor
        # descent was gentle: never faster than ~0.6 m/s
        assert abs(phys.vz) < 0.6

    def test_buoyancy_drift_clamped(self, phys: BlimpPhysics) -> None:
        for _ in range(int(120.0 / 0.02)):
            phys._update_buoyancy(0.02)
        assert abs(phys.buoyancy_gf) <= phys.cfg.buoyancy_clamp_gf + 1e-9

    def test_draft_forces_bounded(self) -> None:
        p = BlimpPhysics(PhysicsConfig(), load_plan("apartment"), seed=7,
                         drafts_enabled=True)
        for _ in range(int(60.0 / 0.02)):
            p._update_draft(0.02)
            dx, dy, dz = p.draft_gf
            cfg = p.cfg
            bound = cfg.draft_amp_gf + cfg.draft_bias_max_gf + 2.5  # + vent fields
            assert abs(dx) <= bound and abs(dy) <= bound
            assert abs(dz) <= cfg.draft_amp_gf * cfg.draft_vertical_frac + 1e-9

    def test_battery_drains_in_flight(self, phys: BlimpPhysics) -> None:
        phys.command(ThrustCommand(forward_gf=10.0, vertical_gf=5.0))
        for _ in range(int(60.0 / 0.02)):
            phys.step(0.02)
        # 20 min full→empty scale: one minute costs ~3-6%
        assert 2.0 < 100.0 - phys.battery_pct < 8.0

    def test_swing_is_underdamped_pendulum(self, phys: BlimpPhysics) -> None:
        phys.command(ThrustCommand(forward_gf=15.0))
        for _ in range(int(2.0 / 0.02)):
            phys.step(0.02)
        phys.command(ThrustCommand())
        peak = 0.0
        crossings = 0
        last_sign = phys.swing >= 0
        for _ in range(int(8.0 / 0.02)):
            phys.step(0.02)
            peak = max(peak, abs(phys.swing))
            sign = phys.swing >= 0
            if sign != last_sign:
                crossings += 1
                last_sign = sign
        assert peak > 0.005  # it swings
        assert crossings >= 3  # and oscillates (underdamped, fins only)

    def test_nose_leads_center(self, phys: BlimpPhysics) -> None:
        phys.heading = 0.0
        nx, ny, nz = phys.nose_position()
        assert nx == pytest.approx(phys.x + phys.cfg.nose_arm_m)
        assert ny == pytest.approx(phys.y)

    def test_frozen_holds_airframe(self, phys: BlimpPhysics) -> None:
        phys.vx = 0.5
        phys.frozen = True
        phys.step(0.02)
        assert phys.vx == 0.0 and phys.vy == 0.0

    def test_net_buoyancy_estimate_tracks_truth(self) -> None:
        """The §G telemetry: hover-duty inversion converges near truth."""
        p = BlimpPhysics(PhysicsConfig(), load_plan("apartment"), seed=3,
                         buoyancy_gf=4.0, drafts_enabled=False)
        p.z = 1.2
        for _ in range(int(30.0 / 0.02)):
            # simple hover servo: cancel vertical velocity + buoyancy
            fz = -40.0 * (p.z - 1.2) - 30.0 * p.vz
            p.command(ThrustCommand(vertical_gf=fz))
            p.step(0.02)
        assert p.net_buoyancy_est_gf == pytest.approx(p.net_buoyancy_true_gf, abs=1.5)
