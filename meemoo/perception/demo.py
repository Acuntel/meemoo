"""Live perception demo — the step-02 gate.

Webcam (or a recorded clip) with an annotated window:

    uv run python -m meemoo.perception.demo                     # webcam
    uv run python -m meemoo.perception.demo --file clip.mp4     # video file

Headless landmark replay (no OpenCV needed — works in CI/SSH):

    uv run python -m meemoo.perception.demo \
        --landmarks tests/fixtures/landmarks/synthetic/fall_forward_ballistic.jsonl

Lying on the floor (or replaying a fall clip) fires candidate.fall then
person.down; standing up fires person.recovered.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from meemoo.core.bus import EventBus
from meemoo.core.config import get_settings
from meemoo.core.logging import setup_logging
from meemoo.perception.calibration import CalibrationState, FloorCalibration, ZoneGrid
from meemoo.perception.landmarks_io import load_clip
from meemoo.perception.signals import SignalExtractor
from meemoo.perception.state_machine import FallStateMachine
from meemoo.perception.thresholds import load_thresholds


def replay_landmarks(path: Path) -> int:
    """Replay a landmark JSONL clip through signals + state machine, print events."""
    clip = load_clip(path)
    a, b = clip.floor_line()
    floor = FloorCalibration.from_line(a, b)
    zones = ZoneGrid()
    for x0, x1, y0, y1 in clip.rest_zones():
        zones.seed_rect(x0, x1, y0, y1)
    th = load_thresholds()
    events: list[tuple[str, dict[str, object]]] = []

    def on_event(name: str, payload: dict[str, object]) -> None:
        events.append((name, payload))
        print(f"  [{payload.get('t', 0):7.2f}s] EVENT {name}  {payload}")  # noqa: T201

    extractor = SignalExtractor(floor)
    machine = FallStateMachine(th, zones, on_event)
    print(f"replaying {clip.name!r} ({len(clip.frames)} frames, label={clip.label})")  # noqa: T201
    last_state = machine.state
    for frame in clip.frames:
        machine.tick(extractor.update(frame))
        if machine.state is not last_state:
            print(f"  [{frame.t:7.2f}s] STATE {last_state.value} -> {machine.state.value}")  # noqa: T201
            last_state = machine.state
    print(f"done: {len(events)} events, final state {machine.state.value}")  # noqa: T201
    return 0


async def run_live(video_file: str | None) -> int:
    """Full pipeline against the webcam (or a video file) with a cv2 window."""
    try:
        import cv2
    except ImportError:
        print("OpenCV missing — run `uv sync --group perception`", file=sys.stderr)  # noqa: T201
        return 1
    from meemoo.perception.pipeline import PerceptionPipeline
    from meemoo.perception.pose import MediaPipePose
    from meemoo.perception.video import FileSource, WebcamSource

    settings = get_settings()
    source = FileSource(video_file) if video_file else WebcamSource(0)
    calibration = CalibrationState()
    # dev default: flat floor prior near the frame bottom until enough upright
    # frames are collected; the real install flow calibrates properly
    calibration.floor.a, calibration.floor.b, calibration.floor.fitted = 0.0, 0.92, True
    bus = EventBus()
    pipeline = PerceptionPipeline(bus, settings, source, MediaPipePose(), calibration)

    sub = bus.subscribe("*")

    async def print_events() -> None:
        async for event in sub:
            print(f"BUS {event.topic}: {event.payload}")  # noqa: T201

    printer = asyncio.create_task(print_events())
    runner = asyncio.create_task(pipeline.run())
    try:
        while not runner.done():
            if pipeline.hub.latest_jpeg is not None:
                import numpy as np

                buf = np.frombuffer(pipeline.hub.latest_jpeg, dtype=np.uint8)
                frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                cv2.imshow("meemoo perception", frame)
            if cv2.waitKey(30) & 0xFF == ord("q"):
                pipeline.stop()
                break
            await asyncio.sleep(0.01)
    finally:
        pipeline.stop()
        await runner
        sub.close()
        printer.cancel()
        cv2.destroyAllWindows()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Meemoo perception demo")
    parser.add_argument("--landmarks", type=Path, help="replay a landmark JSONL clip")
    parser.add_argument("--file", type=str, default=None, help="video file instead of webcam")
    args = parser.parse_args()
    setup_logging(level="INFO")
    if args.landmarks:
        return replay_landmarks(args.landmarks)
    return asyncio.run(run_live(args.file))


if __name__ == "__main__":
    raise SystemExit(main())
