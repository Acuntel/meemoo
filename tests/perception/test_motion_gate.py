"""Motion gate + duty-cycle tier logic — including the §F.3 never-blind rule."""

from __future__ import annotations

from meemoo.perception.motion import MotionGate
from meemoo.perception.pipeline import Tier, next_tier


def test_gate_quiet_on_identical_frames() -> None:
    gate = MotionGate()
    frame = bytes([100] * 1000)
    gate.update(frame)
    assert gate.update(frame) == 0.0


def test_gate_detects_change_fraction() -> None:
    gate = MotionGate()
    gate.update(bytes([100] * 1000))
    half_changed = bytes([200] * 500 + [100] * 500)
    assert abs(gate.update(half_changed) - 0.5) < 0.01


def test_gate_trigger_threshold() -> None:
    gate = MotionGate()
    base = bytes([100] * 1000)
    gate.update(base)
    barely = bytes([200] * 10 + [100] * 990)  # 1% < 2% default
    assert not gate.triggered(barely)
    gate.reset()
    gate.update(base)
    plenty = bytes([200] * 100 + [100] * 900)
    assert gate.triggered(plenty)


def test_gate_first_frame_never_triggers() -> None:
    assert not MotionGate().triggered(bytes([255] * 100))


# ------------------------------------------------------------------ tier logic
def test_idle_stays_idle_without_motion() -> None:
    assert (
        next_tier(
            Tier.IDLE,
            person_visible=False,
            in_candidate_path=False,
            motion_hit=False,
            absent_for=1e9,
        )
        is Tier.IDLE
    )


def test_idle_promotes_on_motion() -> None:
    assert (
        next_tier(
            Tier.IDLE,
            person_visible=False,
            in_candidate_path=False,
            motion_hit=True,
            absent_for=1e9,
        )
        is Tier.ACTIVE
    )


def test_still_person_keeps_pose_running() -> None:
    """§F.3: a person who stops moving must NOT drop us back to the gate —
    a fallen person generates no motion."""
    assert (
        next_tier(
            Tier.ACTIVE,
            person_visible=True,
            in_candidate_path=False,
            motion_hit=False,
            absent_for=0.0,
        )
        is Tier.ACTIVE
    )


def test_briefly_unseen_person_not_dropped() -> None:
    assert (
        next_tier(
            Tier.ACTIVE,
            person_visible=False,
            in_candidate_path=False,
            motion_hit=False,
            absent_for=10.0,
        )
        is Tier.ACTIVE
    )


def test_confirmed_gone_drops_to_idle() -> None:
    assert (
        next_tier(
            Tier.ACTIVE,
            person_visible=False,
            in_candidate_path=False,
            motion_hit=False,
            absent_for=31.0,
        )
        is Tier.IDLE
    )


def test_candidate_path_pins_tracking_even_when_absent() -> None:
    """An occluded person mid-candidate NEVER demotes the pipeline."""
    assert (
        next_tier(
            Tier.ACTIVE,
            person_visible=False,
            in_candidate_path=True,
            motion_hit=False,
            absent_for=1e9,
        )
        is Tier.TRACKING
    )


def test_tracking_relaxes_to_active_after_candidate_clears() -> None:
    assert (
        next_tier(
            Tier.TRACKING,
            person_visible=True,
            in_candidate_path=False,
            motion_hit=False,
            absent_for=0.0,
        )
        is Tier.ACTIVE
    )
