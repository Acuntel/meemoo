"""Extract landmark JSONL from fetched GMDCSA-24 / CaucaFall video clips.

Stage 1 of 2 (the slow, MediaPipe stage). Reads raw videos from
tests/fixtures/clips/raw/{gmdcsa24,caucafall}/ and writes UNANNOTATED
landmark JSONL to tests/fixtures/clips/raw_landmarks/ (gitignored). Stage 2
(tests/fixtures/bake_real.py) merges the committed per-clip annotations and
produces the committed fixtures under tests/fixtures/landmarks/real/.

Requires opencv + mediapipe. The main venv intentionally keeps vision
optional, so use a scratch venv:
    uv venv /tmp/mpvenv --python 3.11
    uv pip install --python /tmp/mpvenv/bin/python \
        "opencv-python>=4.10" "mediapipe>=0.10.14" "numpy>=1.26"
    PYTHONPATH=. /tmp/mpvenv/bin/python -m tests.fixtures.extract_landmarks

Frames are decimated to --max-fps (default 15 — the pipeline's ACTIVE-tier
MediaPipe rate, and the synthetic fixtures' rate) so committed files stay
small and replay matches production cadence.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from meemoo.perception.landmarks_io import write_clip
from meemoo.perception.types import PoseFrame

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
RAW_DIR = Path(__file__).parent / "clips" / "raw"
OUT_DIR = Path(__file__).parent / "clips" / "raw_landmarks"


def extract_clip(
    video_path: Path, out_path: Path, source_name: str, max_fps: float
) -> int:
    import cv2

    from meemoo.perception.pose import MediaPipePose

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    keep_every = max(1, round(fps / max_fps)) if max_fps > 0 else 1
    out_fps = fps / keep_every
    pose = MediaPipePose()
    frames: list[PoseFrame] = []
    try:
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if i % keep_every == 0:
                frames.append(pose.infer(frame, t=i / fps))
            i += 1
    finally:
        cap.release()
        pose.close()
    header = {
        "clip": video_path.stem,
        "fps": round(out_fps, 3),
        "source_fps": round(fps, 3),
        "source": source_name,
        "source_file": video_path.name,
        # floor_line/rest_zones/expect are merged by bake_real.py from
        # tests/fixtures/labels/real_annotations.json before these join the
        # assertion suite; raw extractions are eval data only.
    }
    return write_clip(out_path, header, frames)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clips", type=Path, default=RAW_DIR)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--max-fps", type=float, default=15.0)
    parser.add_argument("--only", help="extract only stems containing this substring")
    args = parser.parse_args()
    videos = sorted(p for p in args.clips.rglob("*") if p.suffix.lower() in VIDEO_EXTS)
    if args.only:
        videos = [v for v in videos if args.only in v.stem]
    if not videos:
        print(f"no videos under {args.clips} — run tests/fixtures/clips/fetch.py first")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for video in videos:
        source = video.parent.name  # gmdcsa24 | caucafall
        out_path = args.out / f"{video.stem}.jsonl"
        n = extract_clip(video, out_path, source, args.max_fps)
        print(f"{video.name} -> {out_path.name} ({n} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
