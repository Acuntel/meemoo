"""MuJoCo rig behavior — skips cleanly when the physics3d group is absent.

Covers the five research/06 SectionG behaviors as MEASUREMENTS against the
engine, plus the capture chain and the adapter contract. Nothing here
asserts docking SUCCESS — the controller's performance is the experiment's
finding (docs/PHYSICS_VALIDATION.md), not a test invariant.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("mujoco")

from meemoo.flight.types import DockPhase, ThrustCommand  # noqa: E402
from sim3d.adapter import Blimp3DAdapter  # noqa: E402
from sim3d.world import MjWorld  # noqa: E402


def _world(**kw: object) -> MjWorld:
    kw.setdefault("seed", 3)
    kw.setdefault("drafts_enabled", False)
    kw.setdefault("buoyancy_gf", 0.0)
    return MjWorld(**kw)  # type: ignore[arg-type]


class TestEnginePhysics:
    def test_engine_owns_added_mass(self) -> None:
        """Virtual mass comes from the compiled model (0.5*rho*V for the
        sphere), and the measured inertia includes it: the blimp coasts."""
        w = _world()
        assert 0.06 < w.added_mass_kg < 0.08
        w.reset_pose(1.0, 0.0, 1.2, 0.0)
        force = 0.0980665  # 10 gf
        for _ in range(50):
            w.step(0.004, external_force_n=(force, 0.0, 0.0))
        _, v = w.velocity()
        m_eff = force / (float(v[0]) / 0.2)
        assert 0.17 < m_eff < 0.23  # 0.125 kg vehicle + ~0.07 engine added

    def test_buoyancy_both_signs(self) -> None:
        for buoy, sign in ((4.0, 1.0), (-4.0, -1.0)):
            w = _world(buoyancy_gf=buoy)
            w.reset_pose(2.0, 0.0, 1.2, 0.0)
            for _ in range(500):
                w.step(0.004)
            dz = w.center_pos[2] - 1.2
            assert dz * sign > 0.05, f"buoyancy {buoy} gf must move z, got {dz}"

    def test_thrust_saturation_is_engine_enforced(self) -> None:
        w = _world()
        w.reset_pose(2.0, 0.0, 1.2, 0.0)
        w.set_motors(forward_gf=100.0, vertical_gf=0.0, yaw_gf=0.0)
        w.step(0.02)
        for c in w.data.ctrl[0:2]:
            assert float(c) <= 10.0 * 9.80665e-3 + 1e-9  # ctrlrange cap

    def test_pendulum_oscillates_at_first_principles_period(self) -> None:
        w = _world()
        w.reset_pose(2.0, 0.0, 1.2, 0.0)
        for _ in range(250):
            w.step(0.004)
        w.data.qvel[4] = 0.8  # pitch-rate kick
        ts, sw = [], []
        for _ in range(2500):
            w.step(0.004)
            rot = w.rotation()
            ts.append(w.t)
            sw.append(math.asin(max(-1.0, min(1.0, float(rot[2, 0])))))
        eq = sum(sw[-400:]) / 400.0
        xs = [s - eq for s in sw]
        crossings = [ts[i] for i in range(1, len(xs)) if xs[i] * xs[i - 1] < 0]
        assert len(crossings) >= 5, "pendulum must oscillate"
        period = 2.0 * (crossings[-1] - crossings[0]) / (len(crossings) - 1)
        assert 1.0 < period < 1.9  # engine says ~1.4 s (2D constant was 2.2)

    def test_drafts_push_the_vehicle(self) -> None:
        w = MjWorld(seed=11, buoyancy_gf=0.0, drafts_enabled=True)
        w.reset_pose(2.0, 0.0, 1.2, 0.0)
        for _ in range(2500):
            w.step(0.004)
        x, y, _ = w.center_pos
        assert math.hypot(x - 2.0, y) > 0.10, "wind must displace a free blimp"


class TestCaptureChain:
    def _approach(self, w: MjWorld, ad: Blimp3DAdapter, *, retention: bool,
                  sim_s: float = 15.0) -> None:
        w.reset_pose(0.68, 0.0, 1.2, math.pi)
        ad.set_retention(retention)
        steps = int(sim_s / 0.01)
        for k in range(steps):
            if k % 25 == 0:
                ad.command(ThrustCommand(forward_gf=8.0))
            ad.step(0.01)
            if w.welded:
                for _ in range(200):
                    ad.step(0.01)
                return

    def test_magnet_weld_seats_and_two_signals_confirm(self) -> None:
        w = _world(buoyancy_gf=1.0)
        ad = Blimp3DAdapter(w, seed=3)
        self._approach(w, ad, retention=True)
        assert w.welded
        assert w.tip_throat_dist < 0.003
        cap = ad.capture()
        assert cap.retention_engaged and cap.contact_continuity and cap.capture_switch
        assert cap.confirmed

    def test_no_retention_means_no_weld(self) -> None:
        w = _world(buoyancy_gf=1.0)
        ad = Blimp3DAdapter(w, seed=3)
        self._approach(w, ad, retention=False, sim_s=10.0)
        assert not w.welded
        assert not ad.capture().retention_engaged

    def test_release_after_remanence_window(self) -> None:
        w = _world(buoyancy_gf=1.0)
        ad = Blimp3DAdapter(w, seed=3)
        self._approach(w, ad, retention=True)
        assert w.welded
        ad.set_retention(False)
        ad.step(0.2)
        assert w.welded, "remanence must hold briefly after magnet-off"
        ad.step(0.6)
        released = not w.welded  # via local: mypy narrows the property itself
        assert released
        for k in range(300):
            if k % 10 == 0:
                ad.command(ThrustCommand(forward_gf=-8.0))
            ad.step(0.01)
        assert w.tip_throat_dist > 0.3, "reverse thrust must back out"


class TestAdapterContract:
    def test_command_latency_is_100ms(self) -> None:
        w = _world()
        ad = Blimp3DAdapter(w, seed=3)
        w.reset_pose(2.0, 0.0, 1.2, 0.0)
        ad.command(ThrustCommand(forward_gf=6.0))
        ad.step(0.05)
        assert w._motors_gf == (0.0, 0.0, 0.0, 0.0)
        ad.step(0.06)
        assert w._motors_gf[0] == 3.0  # 6 gf split across the pair

    def test_camera_fov_and_units(self) -> None:
        w = _world()
        ad = Blimp3DAdapter(w, seed=3)
        w.reset_pose(1.415, 0.1, 1.25, math.pi)  # tip 0.83 m out
        rel = ad.observe()
        assert rel.tracking_valid
        assert abs(rel.range_to_throat_mm - 830.0) < 80.0
        assert abs(rel.lateral_error_mm - 100.0) < 40.0
        assert abs(rel.vertical_error_mm - 50.0) < 40.0
        assert abs(rel.yaw_error_deg) < 1.0
        w.reset_pose(1.0, 2.0, 1.2, math.pi)  # outside the 60 deg half-FOV
        ad._cam_cache = None
        assert not ad.observe().tracking_valid

    def test_pose_swing_sign_matches_2d_convention(self) -> None:
        """Nose pitching UP must read positive swing (2D contract)."""
        w = _world()
        w.reset_pose(2.0, 0.0, 1.2, 0.0)
        w.data.qvel[4] = -0.5  # -y body pitch rate = nose rising
        w.step(0.05)
        ad = Blimp3DAdapter(w, seed=3, pose_noise_m=0.0)
        pose = ad.pose()
        assert pose.swing_rad > 0.005
        assert pose.swing_rate > 0.1


class TestEpisodeRunner:
    def test_short_episode_advances_the_state_machine(self) -> None:
        from sim3d.experiment import run_episode3d

        r = run_episode3d(4, control_hz=50.0, max_sim_s=40.0)
        assert r.end_phase != str(DockPhase.DOCK_REQUESTED)
        assert r.sim_time_s <= 40.0 + 0.1
        # seed 4 docks first-attempt in ~17 s today; keep only the honest
        # floor (it reached the dock's neighborhood), not the success claim
        assert r.min_tip_throat_m < 0.6
