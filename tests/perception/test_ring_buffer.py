"""Skeleton ring buffer: 60 s eviction + JSONL evidence dumps."""

from __future__ import annotations

import random
from pathlib import Path

from meemoo.perception.landmarks_io import load_clip
from meemoo.perception.ring_buffer import SkeletonRingBuffer
from meemoo.perception.types import PoseFrame
from tests.fixtures.synth.body import FLOOR_Y, STAND, make_frame


def _frame(t: float) -> PoseFrame:
    lm = make_frame(STAND, 0.5, FLOOR_Y, 1, random.Random(0), t)
    return PoseFrame(t=t, landmarks=lm)


def test_window_eviction() -> None:
    ring = SkeletonRingBuffer(window_s=60.0)
    for i in range(120 * 5):  # 120 s at 5 fps
        ring.append(_frame(i / 5))
    snapshot = ring.snapshot()
    assert snapshot[-1].t - snapshot[0].t <= 60.0 + 0.21
    assert len(snapshot) <= 60 * 5 + 2


def test_dump_writes_reloadable_jsonl(tmp_path: Path) -> None:
    ring = SkeletonRingBuffer()
    for i in range(50):
        ring.append(_frame(i / 5))
    event_dir = ring.dump(tmp_path, reason="candidate.fall", extra_header={"soft": False})
    skeleton = event_dir / "skeleton.jsonl"
    assert skeleton.exists()
    clip = load_clip(skeleton)
    assert len(clip.frames) == 50
    assert clip.header["reason"] == "candidate.fall"
    assert clip.header["soft"] is False


def test_dump_unique_dirs(tmp_path: Path) -> None:
    ring = SkeletonRingBuffer()
    ring.append(_frame(0.2))
    d1 = ring.dump(tmp_path, reason="a")
    d2 = ring.dump(tmp_path, reason="b")
    assert d1 != d2
