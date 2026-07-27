"""Bake committed real fixtures from raw landmark extractions + annotations.

Stage 2 of 2 (fast, pure-stdlib — no vision deps). Reads:
  tests/fixtures/clips/raw_landmarks/<stem>.jsonl   (gitignored, stage 1)
  tests/fixtures/labels/real_annotations.json       (committed ground truth)
and writes tests/fixtures/landmarks/real/<dataset>/<stem>.jsonl (committed).

Annotations carry per-clip: label, floor_line, rest_zones, expect{...},
lighting, t_impact, and optional tail_hold_s. TAIL-HOLD, disclosed: the
source datasets stop recording a few seconds after impact while the subject
is still on the floor (GMDCSA-24 clips are 4-12 s; thresholds need 6.5 s
grounded for candidate.fall and 15 s for person.down). Where ground truth
says the person remained down at clip end, the bake extends the sequence by
repeating the last landmark-bearing frame at clip cadence for tail_hold_s
seconds. Every held frame is synthetic stillness and the header says so
(tail_hold_s + tail_start_t); nothing about the fall kinematics is altered.

Usage:  uv run python -m tests.fixtures.bake_real
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from meemoo.perception.landmarks_io import load_clip, write_clip

FIXTURES = Path(__file__).parent
RAW_LANDMARKS = FIXTURES / "clips" / "raw_landmarks"
ANNOTATIONS = FIXTURES / "labels" / "real_annotations.json"
REAL_DIR = FIXTURES / "landmarks" / "real"


def bake_clip(raw_path: Path, ann: dict[str, Any], out_dir: Path) -> Path:
    clip = load_clip(raw_path)
    frames = list(clip.frames)
    header = dict(clip.header)
    real_duration = frames[-1].t if frames else 0.0
    header["real_duration_s"] = round(real_duration, 3)

    hold_s = float(ann.get("tail_hold_s", 0.0))
    hold_line: dict[str, Any] | None = None
    if hold_s > 0 and frames:
        header["tail_start_t"] = round(real_duration, 3)
        header["tail_hold_s"] = hold_s
        hold_line = {
            "type": "hold",
            "until": round(real_duration + hold_s, 3),
            "absent": bool(ann.get("tail_absent", False)),
        }

    keys = ("label", "lighting", "floor_line", "rest_zones", "expect",
            "t_impact", "note", "spec_gap")
    for key in keys:
        if key in ann:
            header[key] = ann[key]
    header["annotations"] = "tests/fixtures/labels/real_annotations.json"
    out_path = out_dir / str(header["source"]) / raw_path.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_clip(out_path, header, frames)
    if hold_line is not None:
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(hold_line) + "\n")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_LANDMARKS)
    parser.add_argument("--annotations", type=Path, default=ANNOTATIONS)
    parser.add_argument("--out", type=Path, default=REAL_DIR)
    args = parser.parse_args()
    annotations: dict[str, dict[str, Any]] = json.loads(
        args.annotations.read_text(encoding="utf-8")
    )
    baked = 0
    for stem, ann in sorted(annotations.items()):
        raw_path = args.raw / f"{stem}.jsonl"
        if not raw_path.exists():
            print(f"{stem}: raw landmarks missing (run extract_landmarks first) — skipped")
            continue
        out_path = bake_clip(raw_path, ann, args.out)
        print(f"{stem} -> {out_path.relative_to(FIXTURES)}")
        baked += 1
    unannotated = {
        p.stem for p in args.raw.glob("*.jsonl")
    } - set(annotations)
    for stem in sorted(unannotated):
        print(f"{stem}: extracted but NOT annotated — not baked")
    print(f"baked {baked}/{len(annotations)} annotated clips")
    return 0 if baked == len(annotations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
