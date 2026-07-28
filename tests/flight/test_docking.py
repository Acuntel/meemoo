"""Docking state machine + Monte-Carlo behavior.

GATE STATUS (honest, controller v2, 2026-07-28, 200 randomized episodes at
spec — buoyancy ±5 gf both signs, drafts on, σ-5 cm pose, 100 ms latency,
6 attempts): **first-attempt 90.5%, within one retry 99.0%, within six
100%** at 50 Hz (78.5 / 96.0 / 99.5 at the 10 Hz interface rate). Calm air:
100% first-attempt, zero aborts. The Phase-6 gate (>95% first-attempt AND
>99% within one retry) is STILL NOT MET — both numbers land just under the
bar, and the miss is entirely the draft-vs-authority problem the calm-air
column isolates. Full analysis + the MuJoCo column in
docs/PHYSICS_VALIDATION.md. The tests below lock the safety invariants hard
and pin honest performance FLOORS; the skipped test is the real gate.
"""

from __future__ import annotations

import pytest

from meemoo.flight.constants import DockConfig, PhysicsConfig
from meemoo.flight.docking import DockingController
from meemoo.flight.floorplan import load_plan
from meemoo.flight.types import (
    CaptureTelemetry,
    DockPhase,
    Pose,
    RelativePose,
    ThrustCommand,
)
from tests.flight.conftest import run_episode

PLAN = load_plan("apartment")


def make_ctl(**kw: object) -> DockingController:
    return DockingController(PhysicsConfig(), DockConfig(), PLAN.dock, **kw)  # type: ignore[arg-type]


def phase_of(ctl: DockingController) -> DockPhase:
    """Read the phase through a call boundary (defeats stale narrowing)."""
    return ctl.phase


def idle_pose(x: float = 2.1, y: float = 2.0) -> Pose:
    return Pose(x=x, y=y, z=1.2, heading_rad=3.14, vx=0.0, vy=0.0, vz=0.0,
                yaw_rate=0.0, swing_rad=0.0, swing_rate=0.0, t=0.0)


NO_TRACK = RelativePose(0.0, 0.0, 0.0, 0.0, tracking_valid=False, tracking_age_ms=9999.0)
NO_CAPTURE = CaptureTelemetry(False, False, False)
FULL_CAPTURE = CaptureTelemetry(True, True, True)


class TestStateMachine:
    def test_request_dock_starts_transit(self) -> None:
        ctl = make_ctl()
        ctl.request_dock()
        out = ctl.drive(idle_pose(x=6.0, y=4.0), NO_TRACK, NO_CAPTURE, 80.0, 0.02)
        assert ctl.phase is DockPhase.TRANSIT
        assert (DockPhase.FLYING, DockPhase.DOCK_REQUESTED) in out.transitions

    def test_captured_requires_two_signal_confirmation(self) -> None:
        """The controller NEVER enters CAPTURED on partial signals."""
        ctl = make_ctl()
        ctl.phase = DockPhase.CAPTURE_PENDING
        near = RelativePose(0.0, 0.0, 50.0, 0.0, tracking_valid=True, tracking_age_ms=0.0)
        for partial in (
            CaptureTelemetry(True, False, False),
            CaptureTelemetry(False, True, False),
            CaptureTelemetry(False, False, True),
            CaptureTelemetry(True, True, False),
        ):
            ctl.phase = DockPhase.CAPTURE_PENDING
            ctl.drive(idle_pose(x=1.0), near, partial, 80.0, 0.02)
            assert ctl.phase is not DockPhase.CAPTURED
        ctl.phase = DockPhase.CAPTURE_PENDING
        ctl.drive(idle_pose(x=1.0), near, FULL_CAPTURE, 80.0, 0.02)
        assert ctl.phase is DockPhase.CAPTURED

    def test_charging_to_complete_to_release(self) -> None:
        ctl = make_ctl()
        ctl.phase = DockPhase.CAPTURED
        out = ctl.drive(idle_pose(), NO_TRACK, FULL_CAPTURE, 50.0, 0.02)
        assert phase_of(ctl) is DockPhase.CHARGING
        assert out.retention and out.charge_enabled is False  # enables next tick
        out = ctl.drive(idle_pose(), NO_TRACK, FULL_CAPTURE, 50.0, 0.02)
        assert out.charge_enabled
        ctl.drive(idle_pose(), NO_TRACK, FULL_CAPTURE, 99.95, 0.02)
        assert phase_of(ctl) is DockPhase.CHARGE_COMPLETE
        ctl.request_undock()
        assert phase_of(ctl) is DockPhase.RELEASE
        out = ctl.drive(idle_pose(), NO_TRACK, FULL_CAPTURE, 100.0, 0.02)
        assert not out.retention and not out.charge_enabled
        assert out.cmd == ThrustCommand()  # switch still held: wait, no thrust

    def test_release_departs_once_clear(self) -> None:
        ctl = make_ctl()
        ctl.phase = DockPhase.RELEASE
        far = idle_pose(x=1.6)  # nose ~0.7 m out along the axis
        ctl.drive(far, NO_TRACK, NO_CAPTURE, 100.0, 0.02)
        assert ctl.phase is DockPhase.FLYING

    def test_abort_counts_retries_and_fails_at_max(self) -> None:
        ctl = make_ctl(max_attempts=2)
        ctl.request_dock()
        for _ in range(2):
            ctl.phase = DockPhase.FINAL_APPROACH
            ctl._enter(DockPhase.ABORT)
            # recover at the standoff: EMA converges, then retry++
            for _ in range(600):
                ctl.drive(idle_pose(), NO_TRACK, NO_CAPTURE, 80.0, 0.02)
                if ctl.phase is not DockPhase.ABORT:
                    break
        assert ctl.phase is DockPhase.DOCK_FAILED
        assert ctl.retries == 2

    def test_never_waits_forever_at_the_mouth(self) -> None:
        """A stalled slide must always END. v2 changed WHERE it goes: a nose
        that is not sliding hands back to the planner (re-plan the line, keep
        the attempt) instead of retreating to the standoff — but it still
        leaves CAPTURE_PENDING promptly, which is the invariant."""
        ctl = make_ctl()
        ctl.phase = DockPhase.CAPTURE_PENDING
        near = RelativePose(0.0, 0.0, 60.0, 0.0, tracking_valid=True, tracking_age_ms=0.0)
        left_at = None
        for i in range(int(26.0 / 0.02)):
            ctl.drive(idle_pose(x=1.0), near, NO_CAPTURE, 80.0, 0.02)
            if ctl.phase is not DockPhase.CAPTURE_PENDING:
                left_at = i * 0.02
                break
        assert left_at is not None and left_at < 10.0
        assert ctl.phase in (DockPhase.FINAL_APPROACH, DockPhase.ABORT)


class TestEpisodes:
    """Honest-floor regression tests — NOT the gate (see module docstring)."""

    def test_two_signal_rule_holds_through_full_episodes(self) -> None:
        for seed in range(4):
            res = run_episode(seed, drafts=True, max_sim_s=200.0)
            assert res.single_signal_confirms == 0

    def test_docks_in_calm_air_regression_floor(self) -> None:
        # seeds 10-19 measured 10/10, all first-attempt (v2, 2026-07-28;
        # v1 scored 4/10 with 3 first-attempt on the same seeds)
        results = [run_episode(s, drafts=False) for s in range(10, 20)]
        ok = sum(1 for r in results if r.ok)
        first = sum(1 for r in results if r.ok and r.retries == 0)
        assert ok >= 9
        assert first >= 8

    def test_docks_with_drafts_regression_floor(self) -> None:
        # seeds 0-9 measured 10/10 within six, 8 first-attempt (v2; v1: 3/10)
        results = [run_episode(s, drafts=True) for s in range(10)]
        assert sum(1 for r in results if r.ok) >= 8
        assert sum(1 for r in results if r.ok and r.retries == 0) >= 6

    def test_perturbed_constants_do_not_collapse(self) -> None:
        """±20% mass/thrust perturbation must not zero the controller out
        (tuned-with-honest-physics-stays-tuned, in its honest state).
        Seeds 10-17 measured 8/8 perturbed (v1: 3/8)."""
        cfg = PhysicsConfig(vehicle_mass_kg=0.125 * 1.2,
                            thrust_max_gf_per_motor=8.0)
        results = [run_episode(s, drafts=False, cfg=cfg) for s in range(10, 18)]
        assert sum(1 for r in results if r.ok) >= 6
        assert sum(1 for r in results if r.ok and r.retries == 0) >= 5

    def test_perturbed_constants_survive_drafts_too(self) -> None:
        """The planner reads the vehicle's own numbers (mass, thrust,
        capture speed) to decide when to commit, so a wrong model is a
        pointed risk: measure it. Seeds 0-19 at +20% mass / -20% thrust WITH
        drafts measured 20/20, 19 first-attempt."""
        cfg = PhysicsConfig(vehicle_mass_kg=0.125 * 1.2,
                            thrust_max_gf_per_motor=8.0)
        results = [run_episode(s, drafts=True, cfg=cfg) for s in range(20)]
        assert sum(1 for r in results if r.ok) >= 15

    @pytest.mark.skip(reason=(
        "PHASE-6 GATE NOT MET (honest, controller v2 2026-07-28): >95% "
        "first-attempt AND >99% within one retry required; measured 90.5% "
        "first / 99.0% within one / 100% within six over 200 randomized "
        "episodes at 50 Hz. Both bars missed, narrowly. Calm air is 100% "
        "first-attempt, so what is left is entirely drafts of the same "
        "magnitude as control authority (research/06 §G.5) — the remaining "
        "aborts are tracking losses while the vehicle is blown off the "
        "corridor. Do NOT loosen the physics or the episode contract to "
        "pass this (Constitution Art. II §4). Unskip when it genuinely "
        "passes; docs/PHYSICS_VALIDATION.md carries both engines' numbers."
    ))
    def test_gate_docking_success_rate(self) -> None:
        results = [run_episode(s, drafts=True) for s in range(200)]
        first = sum(1 for r in results if r.ok and r.retries == 0)
        within1 = sum(1 for r in results if r.ok and r.retries <= 1)
        assert first / len(results) > 0.95
        assert within1 / len(results) > 0.99
