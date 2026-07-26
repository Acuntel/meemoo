"""Landmark-clip replay onto a live event bus — demo step 4 without a camera.

The demo script says "lie on the floor (or fall clip via file source)". A
headless machine has neither a webcam nor cv2, so this module replays a
bundled landmark JSONL clip through the REAL ``SignalExtractor`` +
``FallStateMachine`` and publishes the resulting ``candidate.fall`` /
``person.down`` / ``person.recovered`` onto the LIVE bus. The guardian, the
sim, and the dashboard react exactly as if the base-station camera had seen
it — same code path from the state machine outward (Art. IX §2 fixtures; no
video, no cv2, pure landmarks).

Clip names are restricted to the bundled fixture directory — the API layer
passes a NAME, never a path, so there is no traversal surface.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.perception.calibration import FloorCalibration, ZoneGrid
from meemoo.perception.landmarks_io import LandmarkClip, load_clip
from meemoo.perception.signals import SignalExtractor
from meemoo.perception.state_machine import FallStateMachine
from meemoo.perception.thresholds import load_thresholds

logger = logging.getLogger(__name__)

#: Bundled synthetic clips (committed JSONL; see tests/fixtures/README note).
CLIPS_DIR = (
    Path(__file__).resolve().parents[2]
    / "tests" / "fixtures" / "landmarks" / "synthetic"
)

_BUS_TOPICS = {
    "candidate.fall": topics.CANDIDATE_FALL,
    "person.down": topics.PERSON_DOWN,
    "person.recovered": topics.PERSON_RECOVERED,
}

MAX_SPEED = 50.0


def list_clips() -> list[str]:
    """Names of the bundled landmark clips (empty when fixtures are absent)."""
    if not CLIPS_DIR.is_dir():
        return []
    return sorted(p.stem for p in CLIPS_DIR.glob("*.jsonl"))


def clip_path(name: str) -> Path | None:
    """Resolve a bundled clip NAME to its path; None for anything unknown."""
    if name not in list_clips():
        return None
    return CLIPS_DIR / f"{name}.jsonl"


async def replay_to_bus(
    bus: EventBus,
    path: Path,
    *,
    device_id: int = 1,
    speed: float = 1.0,
) -> dict[str, object]:
    """Replay one clip in (scaled) real time, publishing detections to *bus*.

    Returns a summary dict: clip name, frames, events published, final state.
    """
    speed = min(max(speed, 0.1), MAX_SPEED)
    clip: LandmarkClip = load_clip(path)
    a, b = clip.floor_line()
    floor = FloorCalibration.from_line(a, b)
    zones = ZoneGrid()
    for x0, x1, y0, y1 in clip.rest_zones():
        zones.seed_rect(x0, x1, y0, y1)

    pending: list[tuple[str, dict[str, object]]] = []
    machine = FallStateMachine(
        load_thresholds(), zones, lambda name, payload: pending.append((name, payload))
    )
    extractor = SignalExtractor(floor)
    published: list[str] = []
    logger.info(
        "landmark replay starting",
        extra={"fields": {"clip": clip.name, "frames": len(clip.frames),
                          "speed": speed, "device_id": device_id}},
    )
    last_t: float | None = None
    for frame in clip.frames:
        if last_t is not None and frame.t > last_t:
            await asyncio.sleep((frame.t - last_t) / speed)
        last_t = frame.t
        machine.tick(extractor.update(frame))
        flush, pending = pending, []
        for name, payload in flush:
            topic = _BUS_TOPICS.get(name)
            if topic is None:
                logger.info("replay machine event %s", name,
                            extra={"fields": dict(payload)})
                continue
            await bus.publish(topic, dict(payload) | {
                "device_id": device_id,
                "source": "landmark_replay",
                "clip": clip.name,
            })
            published.append(name)
    summary: dict[str, object] = {
        "clip": clip.name,
        "frames": len(clip.frames),
        "events": published,
        "final_state": machine.state.value,
    }
    logger.info("landmark replay done", extra={"fields": summary})
    return summary
