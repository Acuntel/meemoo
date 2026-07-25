"""Pose estimators behind one interface: MediaPipe live, JSONL playback for CI.

MediaPipe Pose Full is the recommended default (research 05 §F.1) — ~15-25 ms
per frame on an N100-class CPU. The import and model load are lazy so the
package (and CI) works without mediapipe installed; fixtures use
LandmarkPlayback instead, which replays committed JSONL landmark clips.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from meemoo.perception.landmarks_io import LandmarkClip
from meemoo.perception.types import PoseFrame

logger = logging.getLogger(__name__)


class PoseEstimator(Protocol):
    """One frame in, one PoseFrame out (landmarks None == no person)."""

    def infer(self, frame_bgr: Any, t: float) -> PoseFrame: ...

    def close(self) -> None: ...


class MediaPipePose:
    """BlazePose GHUM Full via the classic mediapipe Pose solution API."""

    def __init__(self, model_complexity: int = 1) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError(
                "mediapipe not installed — run `uv sync --group perception`"
            ) from exc
        self._mp = mp
        self._pose = mp.solutions.pose.Pose(
            model_complexity=model_complexity,  # 1 = Full (§F.1 recommended)
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def infer(self, frame_bgr: Any, t: float) -> PoseFrame:
        rgb = frame_bgr[:, :, ::-1]
        result = self._pose.process(rgb)
        lm = getattr(result, "pose_landmarks", None)
        if lm is None:
            return PoseFrame(t=t, landmarks=None)
        landmarks = [[p.x, p.y, p.z, p.visibility] for p in lm.landmark]
        return PoseFrame(t=t, landmarks=landmarks)

    def close(self) -> None:
        self._pose.close()


class LandmarkPlayback:
    """Replays a committed landmark clip as if it were a live pose stream."""

    def __init__(self, clip: LandmarkClip) -> None:
        self._frames = clip.frames
        self._i = 0

    @property
    def exhausted(self) -> bool:
        return self._i >= len(self._frames)

    def next_frame(self) -> PoseFrame | None:
        """The next recorded frame, or None at end of clip."""
        if self.exhausted:
            return None
        frame = self._frames[self._i]
        self._i += 1
        return frame

    def infer(self, frame_bgr: Any, t: float) -> PoseFrame:
        nxt = self.next_frame()
        return PoseFrame(t=t, landmarks=None) if nxt is None else nxt

    def close(self) -> None:
        self._i = len(self._frames)
