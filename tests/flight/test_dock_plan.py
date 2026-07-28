"""Unit tests for the controller-v2 pieces: draft observer, commit planner,
in-funnel slide monitor.

Each test below pins a rule that a measured failure bought. The episode-level
numbers those failures came from are in docs/PHYSICS_VALIDATION.md; these are
the fast regression gates for the logic itself.
"""

from __future__ import annotations

import math

from meemoo.flight.constants import GF_TO_N, DockConfig, PhysicsConfig
from meemoo.flight.dock_plan import ApproachPlanner
from meemoo.flight.dock_slide import SlideMonitor
from meemoo.flight.docking import _AxisErrors
from meemoo.flight.draft import DraftEstimator
from meemoo.flight.types import CaptureTelemetry, Pose, ThrustCommand

AXIS = (1.0, 0.0)  # dock axis along +x, so l̂ = +y
NO_CAPTURE = CaptureTelemetry(False, False, False)
CONTACT = CaptureTelemetry(False, True, False)


def err(
    range_m: float = 0.5,
    lateral_m: float = 0.0,
    vertical_m: float = 0.0,
    v_axis: float = 0.10,
    v_lat: float = 0.0,
    fresh: bool = True,
) -> _AxisErrors:
    return _AxisErrors(range_m, lateral_m, vertical_m, v_axis, v_lat, fresh)


class TestDraftEstimator:
    """The blimp is its own anemometer (research/06 §G.5)."""

    def _fly(
        self, draft_gf: tuple[float, float], thrust_gf: float, secs: float = 12.0
    ) -> DraftEstimator:
        """Integrate a point mass under thrust + an unknown steady force,
        feeding the observer only what the base station would really know."""
        cfg = PhysicsConfig()
        est = DraftEstimator(cfg)
        m = cfg.effective_mass_kg
        vx = vy = 0.0
        x = y = 0.0
        dt = 0.02
        t = 0.0
        while t < secs:
            speed = math.hypot(vx, vy)
            drag = cfg.drag_quad_n_per_mps2 * speed + cfg.drag_lin_n_per_mps
            fx = thrust_gf * GF_TO_N + draft_gf[0] * GF_TO_N - drag * vx
            fy = draft_gf[1] * GF_TO_N - drag * vy
            vx += fx / m * dt
            vy += fy / m * dt
            x += vx * dt
            y += vy * dt
            t += dt
            pose = Pose(x=x, y=y, z=1.2, heading_rad=0.0, vx=vx, vy=vy, vz=0.0,
                        yaw_rate=0.0, swing_rad=0.0, swing_rate=0.0, t=t)
            est.update(pose, dt)
            est.record(ThrustCommand(forward_gf=thrust_gf), t)
        return est

    def test_recovers_a_steady_crosswind(self) -> None:
        est = self._fly((0.0, 2.5), thrust_gf=4.0)
        assert abs(est.estimate.y_gf - 2.5) < 0.6
        assert abs(est.estimate.x_gf) < 0.8
        assert est.estimate.confidence > 0.7

    def test_sign_follows_the_dock_lateral_axis(self) -> None:
        """lateral_gf projects onto l̂ = (−a_y, a_x); the crab law depends on
        that sign being right, and a flipped one steers INTO the drift."""
        est = self._fly((0.0, -3.0), thrust_gf=4.0)
        assert est.estimate.lateral_gf(AXIS) < -1.5

    def test_zero_wind_reads_as_zero(self) -> None:
        est = self._fly((0.0, 0.0), thrust_gf=5.0)
        assert abs(est.estimate.lateral_gf(AXIS)) < 0.7

    def test_learning_can_be_frozen(self) -> None:
        """Inside the cone the wall holds the nose still; commanded thrust
        with no acceleration is the wall talking, not the wind."""
        cfg = PhysicsConfig()
        est = DraftEstimator(cfg)
        for i in range(400):
            t = i * 0.02
            pose = Pose(x=0.0, y=0.0, z=1.2, heading_rad=0.0, vx=0.0, vy=0.0,
                        vz=0.0, yaw_rate=0.0, swing_rad=0.0, swing_rate=0.0, t=t)
            est.update(pose, 0.02, learn=False)
            est.record(ThrustCommand(forward_gf=8.0), t)
        assert est.estimate.x_gf == 0.0
        assert est.estimate.y_gf == 0.0

    def test_reset_forgets(self) -> None:
        est = self._fly((0.0, 3.0), thrust_gf=4.0)
        assert abs(est.estimate.y_gf) > 1.0
        est.reset()
        assert est.estimate.y_gf == 0.0
        assert est.estimate.confidence == 0.0


class TestApproachPlanner:
    def planner(self) -> ApproachPlanner:
        return ApproachPlanner(PhysicsConfig(), DockConfig())

    def _settle(self, pl: ApproachPlanner, e: _AxisErrors, ticks: int = 40,
                draft: float = 0.0) -> object:
        plan = pl.update(e, draft, 0.02)
        for _ in range(ticks):
            plan = pl.update(e, draft, 0.02)
        return plan

    def test_cruises_beyond_the_gate(self) -> None:
        """No commit decision is made a metre out — that is where cross error
        is cheap to fix, so the leg just flies."""
        pl = self.planner()
        plan = self._settle(pl, err(range_m=1.1, lateral_m=0.25))
        assert not plan.hold  # type: ignore[attr-defined]
        assert pl.commits == 0

    def test_commits_on_a_line_the_airframe_can_hold(self) -> None:
        pl = self.planner()
        plan = self._settle(pl, err(range_m=0.5, lateral_m=0.02, v_lat=0.0))
        assert plan.committed  # type: ignore[attr-defined]
        assert not plan.hold  # type: ignore[attr-defined]

    def test_holds_instead_of_going_around_when_the_line_is_bad(self) -> None:
        """341 (2D) / 506 (MuJoCo) v1 aborts fired inside 30 cm with a 5-15 cm
        error. Holding costs seconds; a go-around costs an attempt."""
        pl = self.planner()
        plan = self._settle(pl, err(range_m=0.4, lateral_m=0.05, v_lat=0.25))
        assert plan.hold  # type: ignore[attr-defined]
        assert plan.abort is None  # type: ignore[attr-defined]
        assert plan.hold_r_m >= 0.30  # type: ignore[attr-defined]

    def test_a_strong_draft_closes_the_window(self) -> None:
        """Holding the crab costs lateral authority whether or not the
        estimator is confident — the wind does not care."""
        pl = self.planner()
        plan = self._settle(pl, err(range_m=0.5, lateral_m=0.0), draft=9.0)
        assert plan.hold  # type: ignore[attr-defined]

    def test_will_not_commit_already_too_fast_to_be_captured(self) -> None:
        pl = self.planner()
        fast = err(range_m=0.5, lateral_m=0.0,
                   v_axis=DockConfig().v_max_capture_mps * 1.5)
        plan = self._settle(pl, fast)
        assert plan.hold  # type: ignore[attr-defined]

    def test_speed_profile_stays_under_the_capture_limit(self) -> None:
        """v1 equilibrated ABOVE v_max_capture and the funnel rejected
        contacts the controller never saw."""
        pl = self.planner()
        cap = DockConfig().v_max_capture_mps
        for r in (0.05, 0.2, 0.45, 0.62, 1.5):
            plan = pl.update(err(range_m=r), 0.0, 0.02)
            assert 0.0 < plan.v_des <= 0.9 * cap

    def test_wave_off_replans_then_aborts_only_when_the_budget_is_spent(
        self,
    ) -> None:
        pl = ApproachPlanner(PhysicsConfig(), DockConfig(), max_commits=2)
        aborted = False
        replans = 0
        good = err(range_m=0.5, lateral_m=0.0, v_lat=0.0)
        bad = err(range_m=0.5, lateral_m=0.60, v_lat=0.80)
        for _ in range(4):
            for _ in range(60):
                p = pl.update(good, 0.0, 0.02)
                if p.abort:
                    aborted = True
            for _ in range(60):
                p = pl.update(bad, 0.0, 0.02)
                replans += int(p.replanned)
                aborted = aborted or p.abort is not None
        assert replans >= 1  # corrected the line without spending an attempt
        assert aborted  # but the budget is finite


class TestSlideMonitor:
    def test_never_aborts_while_the_range_is_shrinking(self) -> None:
        """THE regression gate: 209 MuJoCo aborts, 35 within 5 cm of the
        magnet, came from judging a multi-second slide on single noisy
        samples of a σ-5 cm dead reckoning."""
        sm = SlideMonitor()
        sm.reset(err(range_m=0.08, lateral_m=0.0, fresh=False))
        r = 0.08
        noisy = [0.06, -0.09, 0.11, -0.07, 0.08, -0.10, 0.05, -0.06] * 12
        for i in range(96):
            r -= 0.004  # a real 0.05 m/s slide at 80 Hz-ish ticks
            v = sm.update(
                err(range_m=r, lateral_m=noisy[i], v_axis=0.05, fresh=False),
                NO_CAPTURE, 0.02,
            )
            assert v.abort is None
            assert not v.back_to_approach

    def test_a_single_bounce_sample_does_not_fire_the_retreat_gate(self) -> None:
        sm = SlideMonitor()
        sm.reset(err(range_m=0.05, fresh=False))
        r = 0.05
        for i in range(50):
            r -= 0.002
            spike = -0.4 if i == 20 else 0.05  # one noisy retreat sample
            v = sm.update(err(range_m=r, v_axis=spike, fresh=False),
                          NO_CAPTURE, 0.02)
            assert v.abort is None

    def test_contact_telemetry_outranks_dead_reckoning(self) -> None:
        """Once the charge rings touch, a wild dead-reckoned lateral is the
        pose estimate being wrong, not the vehicle being beside the dock."""
        sm = SlideMonitor()
        sm.reset(err(range_m=0.02, fresh=False))
        for _ in range(300):
            v = sm.update(
                err(range_m=-0.34, lateral_m=0.6, v_axis=-0.2, fresh=False),
                CONTACT, 0.02,
            )
            assert v.abort is None
            assert v.hold_thrust

    def test_holds_slide_thrust_from_the_mouth_and_escalates_on_a_stall(
        self,
    ) -> None:
        sm = SlideMonitor()
        sm.reset(err(range_m=0.06, fresh=False))
        v = sm.update(err(range_m=0.015, v_axis=0.05, fresh=False),
                      NO_CAPTURE, 0.02)
        assert v.hold_thrust  # latched on a raw sample inside the mouth
        assert v.push_gf == 6.0
        for _ in range(150):  # 3 s of no progress
            v = sm.update(err(range_m=0.015, v_axis=0.0, fresh=False),
                          NO_CAPTURE, 0.02)
        assert v.push_gf > 6.0  # push harder before giving up (§B.1)
        assert v.push_gf <= 12.0

    def test_leaning_on_the_rim_replans_rather_than_spending_an_attempt(
        self,
    ) -> None:
        sm = SlideMonitor()
        sm.reset(err(range_m=0.05, fresh=False))
        out = None
        for _ in range(int(8.0 / 0.02)):
            out = sm.update(err(range_m=0.05, v_axis=0.0, fresh=False),
                            NO_CAPTURE, 0.02)
            if out.back_to_approach:
                break
        assert out is not None and out.back_to_approach
        assert out.abort is None

    def test_growing_lateral_means_we_are_not_in_a_cone(self) -> None:
        """A funnel narrows: inside it |lateral| can only shrink."""
        sm = SlideMonitor()
        sm.reset(err(range_m=0.02, lateral_m=0.02, fresh=False))
        out = None
        lat = 0.02
        for _ in range(200):
            lat += 0.004
            out = sm.update(err(range_m=0.0, lateral_m=lat, v_axis=0.0,
                                fresh=False), NO_CAPTURE, 0.02)
            if out.back_to_approach:
                break
        assert out is not None and out.back_to_approach

    def test_a_genuine_bypass_still_aborts(self) -> None:
        """Deep past the mouth plane, far off axis from the start (so the
        narrowing-cone test has nothing to catch), never any contact."""
        sm = SlideMonitor()
        sm.reset(err(range_m=0.05, lateral_m=0.45, fresh=False))
        out = None
        for _ in range(300):
            out = sm.update(
                err(range_m=-0.5, lateral_m=0.45, v_axis=0.2, fresh=False),
                NO_CAPTURE, 0.02,
            )
            if out.abort:
                break
        assert out is not None and out.abort is not None
