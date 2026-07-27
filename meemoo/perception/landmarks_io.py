"""Landmark-clip JSONL schema: read/write (fixtures, ring-buffer dumps).

Schema (one JSON object per line):
  line 1: {"type": "header", "clip": ..., "fps": ..., "source": ...,
           "floor_line": [a, b], "rest_zones": [[x0,x1,y0,y1], ...],
           "label": "fall|adl|recovery", ...}
  rest:   {"t": <sec>, "lm": [[x, y, z, vis] * 33]}  — or {"t": ..., "lm": null}
          for frames where no person was found.
  last (optional): {"type": "hold", "until": <sec>, "absent": bool} — a
          disclosed TAIL-HOLD: the loader repeats the last landmark-bearing
          frame (or absence, when "absent") at header-fps cadence up to
          `until`. Real fall datasets stop recording seconds after impact
          while the subject is still on the floor; the hold line represents
          "nothing changed after the camera stopped" without committing
          thousands of duplicate frames (see tests/fixtures/bake_real.py).

Coordinates are image-normalized, y DOWN (MediaPipe convention). Committing
landmark sequences rather than video keeps CI fast and hermetic and is
privacy-preserving (research 05 §A.6, §B.4).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from meemoo.perception.types import PoseFrame


@dataclass(slots=True)
class LandmarkClip:
    """A parsed landmark clip: header metadata + time-ordered pose frames."""

    header: dict[str, Any] = field(default_factory=dict)
    frames: list[PoseFrame] = field(default_factory=list)

    @property
    def name(self) -> str:
        return str(self.header.get("clip", "unnamed"))

    @property
    def label(self) -> str:
        return str(self.header.get("label", "unknown"))

    @property
    def duration(self) -> float:
        return self.frames[-1].t if self.frames else 0.0

    def floor_line(self) -> tuple[float, float]:
        a, b = self.header.get("floor_line", [0.0, 0.92])
        return float(a), float(b)

    def rest_zones(self) -> list[tuple[float, float, float, float]]:
        return [
            (float(z[0]), float(z[1]), float(z[2]), float(z[3]))
            for z in self.header.get("rest_zones", [])
        ]


def load_clip(path: Path) -> LandmarkClip:
    """Load a landmark JSONL clip from disk."""
    clip = LandmarkClip()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") == "header":
                clip.header = obj
                continue
            if obj.get("type") == "hold":
                _expand_hold(clip, obj)
                continue
            lm = obj.get("lm")
            clip.frames.append(PoseFrame(t=float(obj["t"]), landmarks=lm))
    return clip


def _expand_hold(clip: LandmarkClip, obj: dict[str, Any]) -> None:
    """Expand a tail-hold line into repeated frames at header-fps cadence."""
    if not clip.frames:
        return
    fps = float(clip.header.get("fps", 15.0))
    until = float(obj["until"])
    source: list[list[float]] | None = None
    if not obj.get("absent", False):
        for frame in reversed(clip.frames):
            if frame.landmarks is not None:
                source = frame.landmarks
                break
    t = clip.frames[-1].t
    step = 1.0 / max(fps, 1e-3)
    while t + step <= until + 1e-9:
        t += step
        clip.frames.append(PoseFrame(t=t, landmarks=source))


def _round_lm(lm: list[list[float]]) -> list[list[float]]:
    return [[round(p[0], 3), round(p[1], 3), round(p[2], 2), round(p[3], 2)] for p in lm]


def write_clip(
    path: Path, header: dict[str, Any], frames: Iterable[PoseFrame]
) -> int:
    """Write a landmark clip as JSONL; returns the number of frames written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "header", **header}) + "\n")
        for frame in frames:
            lm = None if frame.landmarks is None else _round_lm(frame.landmarks)
            fh.write(json.dumps({"t": round(frame.t, 3), "lm": lm}) + "\n")
            n += 1
    return n
