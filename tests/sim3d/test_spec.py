"""sim3d constants + pure helpers — runs WITHOUT mujoco installed."""

from __future__ import annotations

from sim3d.spec import (
    Episode3DResult,
    Rig3DConfig,
    failure_histogram,
    mix_thrust,
    success_rates,
)


class TestGeometry:
    def test_total_mass_is_the_125_g_vehicle(self) -> None:
        assert abs(Rig3DConfig().total_mass - 0.125) < 1e-9

    def test_probe_reaches_the_throat_with_rim_clearance(self) -> None:
        """The assigned cone forces the probe length: seated sphere center
        must clear the mouth rim (the finding documented in the module)."""
        cfg = Rig3DConfig()
        assert cfg.seated_center_x >= cfg.rim_seat_x + 0.003
        assert abs((cfg.seated_center_x + cfg.cone_depth) - cfg.tip_reach) < 1e-9

    def test_cup_is_inside_the_spec_depth(self) -> None:
        cfg = Rig3DConfig()
        assert cfg.cup_depth < cfg.cone_depth
        assert cfg.cup_exit_radius > cfg.tip_radius  # tip passes through


class TestMixer:
    def test_matches_2d_per_motor_saturation(self) -> None:
        cfg = Rig3DConfig()
        left, right, v1, v2 = mix_thrust(20.0, 0.0, 0.0, cfg)
        assert left == right == 10.0  # forward saturates per motor
        left, right, _, _ = mix_thrust(0.0, 0.0, 8.0, cfg)
        assert left == -5.0 and right == 8.0  # reverse cap weaker
        _, _, v1, v2 = mix_thrust(0.0, -30.0, 0.0, cfg)
        assert v1 == v2 == -5.0

    def test_forward_and_yaw_share_authority(self) -> None:
        cfg = Rig3DConfig()
        left, right, _, _ = mix_thrust(16.0, 0.0, 4.0, cfg)
        assert right == 10.0  # saturated: yaw stole forward headroom
        assert left == 4.0


class TestSummaries:
    @staticmethod
    def _ep(seed: int, ok: bool, retries: int, phase: str) -> Episode3DResult:
        return Episode3DResult(
            seed=seed, ok=ok, retries=retries, sim_time_s=50.0, buoyancy_gf=1.0,
            end_phase=phase, mouth_entries=1, contact_speed_mps=0.1,
            min_tip_throat_m=0.0 if ok else 0.4,
        )

    def test_rates_and_failure_modes(self) -> None:
        eps = [
            self._ep(0, True, 0, "CAPTURED"),
            self._ep(1, True, 1, "CAPTURED"),
            self._ep(2, False, 6, "DOCK_FAILED"),
            self._ep(3, False, 2, "ALIGN"),
        ]
        rates = success_rates(eps)
        assert rates["first_attempt"] == 0.25
        assert rates["within_one_retry"] == 0.5
        assert rates["within_max_attempts"] == 0.5
        hist = failure_histogram(eps)
        assert hist["captured"] == 2
        assert hist["max_attempts"] == 1
        assert hist["timeout_ALIGN"] == 1
