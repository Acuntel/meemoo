"""Generate the committed synthetic landmark fixtures (deterministic).

Run from the repo root:  uv run python -m tests.fixtures.generate_synthetic

Real-dataset landmark extraction (GMDCSA-24 + CaucaFall) is the target end
state (research 05 §B); these synthetic clips keep CI hermetic until the raw
clips have been fetched (tests/fixtures/clips/fetch.py) and extracted
(tests/fixtures/extract_landmarks.py) on a machine with mediapipe installed.
Every clip embeds its own expectations in the header, so tests iterate
generically over whatever clips exist. Clip specs live in
tests/fixtures/synth/clips_falls.py and clips_daily.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from meemoo.perception.landmarks_io import write_clip
from tests.fixtures.synth.clips_daily import build_daily_specs
from tests.fixtures.synth.clips_falls import build_fall_specs
from tests.fixtures.synth.compiler import ClipSpec, compile_clip

OUT_DIR = Path(__file__).parent / "landmarks" / "synthetic"
LABELS_PATH = Path(__file__).parent / "labels" / "synthetic.json"


def build_specs() -> list[ClipSpec]:
    return build_fall_specs() + build_daily_specs()


# OmniFall 16-class taxonomy (research 05 §B.4): the classes each clip exercises.
_OMNIFALL: dict[str, list[str]] = {
    "fall": ["walk", "fall", "fallen"],
    "adl": ["walk", "sit_down", "sitting", "lie_down", "lying", "stand_up"],
    "recovery": ["walk", "fall", "fallen", "stand_up", "walk"],
}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    labels: dict[str, dict[str, object]] = {}
    for spec in build_specs():
        header, frames = compile_clip(spec)
        path = OUT_DIR / f"{spec.name}.jsonl"
        n = write_clip(path, header, frames)
        labels[spec.name] = {
            "label": spec.label,
            "omnifall_classes": _OMNIFALL[spec.label],
            "frames": n,
            "duration_s": round(frames[-1].t, 1),
        }
        print(f"wrote {path.name}: {n} frames, {frames[-1].t:.1f}s")
    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {LABELS_PATH} ({len(labels)} clips)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
