"""Extract landmark JSONL from fetched GMDCSA-24 / CaucaFall video clips.

Requires the perception extras (`uv sync --group perception`) and fetched raw
clips (tests/fixtures/clips/fetch.py). Committed landmark sequences — not
video — are what CI runs against (research 05 §B.4): fast, hermetic, and no
redistribution concerns (landmark coordinates are derived data).

Usage:
    uv run python -m tests.fixtures.extract_landmarks \
        --clips tests/fixtures/clips/gmdcsa --out tests/fixtures/landmarks/gmdcsa
"""

from __future__ import annotations

import argparse
from pathlib import Path

from meemoo.perception.landmarks_io import write_clip
from meemoo.perception.types import PoseFrame

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def extract_clip(video_path: Path, out_path: Path, source_name: str) -> int:
    import cv2

    from meemoo.perception.pose import MediaPipePose

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    pose = MediaPipePose()
    frames: list[PoseFrame] = []
    try:
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(pose.infer(frame, t=i / fps))
            i += 1
    finally:
        cap.release()
        pose.close()
    header = {
        "clip": video_path.stem,
        "fps": fps,
        "source": source_name,
        "source_file": video_path.name,
        # NOTE: floor_line/rest_zones/expect must be annotated per-clip before
        # these join the assertion suite; until then they serve as eval data.
    }
    return write_clip(out_path, header, frames)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clips", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", default="gmdcsa24")
    args = parser.parse_args()
    videos = sorted(
        p for p in args.clips.rglob("*") if p.suffix.lower() in VIDEO_EXTS
    )
    if not videos:
        print(f"no videos under {args.clips} — run tests/fixtures/clips/fetch.py first")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for video in videos:
        out_path = args.out / f"{video.stem}.jsonl"
        n = extract_clip(video, out_path, args.source)
        print(f"{video.name} -> {out_path.name} ({n} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
