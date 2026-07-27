"""ReacquiringPose gating: the low-confidence pass runs ONLY for a track that
was being followed and is now unaccounted for.

The threshold is not what protects precision here — the gate is. These tests
pin the gate, because a fallback that runs on every frame would be a plain
sensitivity change and would earn every false detection the cheap detector
makes (real-data finding 3; research 05 §A.4).
"""

from __future__ import annotations

from typing import Any

from meemoo.perception.pose import ReacquiringPose
from meemoo.perception.types import Landmarks, PoseFrame

LM: Landmarks = [[0.5, 0.5, 0.0, 0.9] for _ in range(33)]


class FakePose:
    """Returns a person on the frames listed in `present_at`, else nothing."""

    def __init__(self, present_at: set[int]) -> None:
        self.present_at = present_at
        self.calls: list[float] = []
        self.closed = False

    def infer(self, frame_bgr: Any, t: float) -> PoseFrame:
        self.calls.append(t)
        found = int(round(t * 10)) in self.present_at
        return PoseFrame(t=t, landmarks=LM if found else None)

    def close(self) -> None:
        self.closed = True


def _run(
    primary: FakePose, fallback: FakePose, ticks: int = 40, **kw: float
) -> tuple[ReacquiringPose, list[PoseFrame]]:
    pose = ReacquiringPose(primary, fallback, **kw)
    return pose, [pose.infer(None, i / 10.0) for i in range(ticks)]


def test_fallback_is_never_consulted_while_the_primary_sees_the_person() -> None:
    primary = FakePose(set(range(40)))
    fallback = FakePose(set(range(40)))
    pose, frames = _run(primary, fallback)
    assert all(f.present for f in frames)
    assert fallback.calls == []
    assert pose.reacquired_frames == 0


def test_fallback_recovers_a_track_the_primary_dropped() -> None:
    """The miss class: tracked, then lost mid-scene, never seen leaving."""
    primary = FakePose(set(range(10)))  # loses them at t=1.0 and never recovers
    fallback = FakePose(set(range(40)))  # cheap detector still sees the body
    pose, frames = _run(primary, fallback)
    assert all(f.present for f in frames), "person should stay tracked throughout"
    assert pose.reacquired_frames == 30
    assert fallback.calls, "fallback must have run"


def test_empty_room_never_wakes_the_fallback() -> None:
    """Cold start with nobody there: the cheap detector must stay off."""
    primary = FakePose(set())
    fallback = FakePose(set(range(40)))
    pose, frames = _run(primary, fallback)
    assert not any(f.present for f in frames)
    assert fallback.calls == []
    assert pose.reacquired_frames == 0


def test_a_person_seen_leaving_is_not_chased_past_the_grace_window() -> None:
    primary = FakePose(set(range(5)))  # walks out at t=0.5
    fallback = FakePose(set())  # and is genuinely gone
    pose, frames = _run(primary, fallback, grace_s=1.0)
    assert not frames[-1].present
    # tried only inside the grace window, then gave up for good
    assert fallback.calls and max(fallback.calls) <= 1.5
    assert len(fallback.calls) < 15


def test_fallback_only_carry_is_capped() -> None:
    """A phantom the primary never corroborates must not be tracked forever."""
    primary = FakePose(set(range(5)))
    fallback = FakePose(set(range(40)))
    pose, frames = _run(primary, fallback, max_carry_s=1.0)
    assert frames[10].present, "carry should hold inside the cap"
    assert not frames[-1].present, "carry must expire at the cap"


def test_close_closes_both_estimators() -> None:
    primary, fallback = FakePose(set()), FakePose(set())
    pose = ReacquiringPose(primary, fallback)
    pose.close()
    assert primary.closed and fallback.closed
