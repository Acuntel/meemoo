"""Pipeline integration with fakes: bus wiring, presence, evidence dumps.

Runs entirely without OpenCV/MediaPipe — pose comes from committed landmark
playback; the 'camera frame' is an opaque object the fakes never inspect.
"""

from __future__ import annotations

from pathlib import Path

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.config import Settings
from meemoo.perception.calibration import CalibrationState, FloorCalibration, ZoneGrid
from meemoo.perception.landmarks_io import load_clip
from meemoo.perception.pipeline import PerceptionPipeline, Tier
from meemoo.perception.pose import LandmarkPlayback
from tests.perception.harness import SYNTHETIC_DIR


class _NoSource:
    """Satisfies VideoSource; run() is never used in these tests."""

    fps = 15.0

    def read(self) -> object | None:
        return None

    def close(self) -> None:
        return None


async def _run_clip_through_pipeline(
    clip_name: str, tmp_path: Path, bare_settings: Settings
) -> tuple[PerceptionPipeline, list[tuple[str, dict[str, object]]]]:
    clip = load_clip(SYNTHETIC_DIR / f"{clip_name}.jsonl")
    a, b = clip.floor_line()
    zones = ZoneGrid()
    for x0, x1, y0, y1 in clip.rest_zones():
        zones.seed_rect(x0, x1, y0, y1)
    calibration = CalibrationState(floor=FloorCalibration.from_line(a, b), zones=zones)
    calibration.started_at = 0.0  # learning phase long over
    bus = EventBus()
    seen: list[tuple[str, dict[str, object]]] = []
    sub = bus.subscribe("*")
    pipeline = PerceptionPipeline(
        bus,
        bare_settings,
        source=_NoSource(),
        pose=LandmarkPlayback(clip),
        calibration=calibration,
        events_dir=tmp_path / "events",
    )
    pipeline.tier = Tier.ACTIVE  # skip the cv2-backed motion gate
    dummy_frame = object()
    for _ in clip.frames:
        await pipeline.step(dummy_frame)
    while not sub._queue.empty():  # drain synchronously delivered events
        event = await sub.get()
        seen.append((event.topic, dict(event.payload)))
    sub.close()
    return pipeline, seen


async def test_fall_clip_publishes_bus_events(
    tmp_path: Path, bare_settings: Settings
) -> None:
    pipeline, seen = await _run_clip_through_pipeline(
        "recovery_after_down", tmp_path, bare_settings
    )
    names = [n for (n, _) in seen]
    assert names.count(topics.PERSON_DETECTED) == 1
    assert topics.CANDIDATE_FALL in names
    assert topics.PERSON_DOWN in names
    assert topics.PERSON_RECOVERED in names
    # ordering: detected -> candidate -> down -> recovered
    order = [
        names.index(topics.PERSON_DETECTED),
        names.index(topics.CANDIDATE_FALL),
        names.index(topics.PERSON_DOWN),
        names.index(topics.PERSON_RECOVERED),
    ]
    assert order == sorted(order)


async def test_candidate_dumps_ring_buffer_evidence(
    tmp_path: Path, bare_settings: Settings
) -> None:
    _, seen = await _run_clip_through_pipeline(
        "fall_forward_ballistic", tmp_path, bare_settings
    )
    candidates = [p for (n, p) in seen if n == topics.CANDIDATE_FALL]
    assert candidates
    evidence_dir = Path(str(candidates[0]["evidence_dir"]))
    skeleton = evidence_dir / "skeleton.jsonl"
    assert skeleton.exists()
    dumped = load_clip(skeleton)
    assert dumped.frames  # the 60 s pre-candidate skeleton window
    assert dumped.header["reason"] == "candidate.fall"


async def test_adl_clip_publishes_no_alarms(
    tmp_path: Path, bare_settings: Settings
) -> None:
    _, seen = await _run_clip_through_pipeline("adl_lie_couch", tmp_path, bare_settings)
    names = [n for (n, _) in seen]
    assert topics.CANDIDATE_FALL not in names
    assert topics.PERSON_DOWN not in names
    assert names.count(topics.PERSON_DETECTED) == 1


async def test_tier_holds_active_while_person_tracked(
    tmp_path: Path, bare_settings: Settings
) -> None:
    pipeline, _ = await _run_clip_through_pipeline(
        "fall_forward_ballistic", tmp_path, bare_settings
    )
    # candidate path pins TRACKING at end of clip; never fell back to IDLE
    assert pipeline.tier is Tier.TRACKING
