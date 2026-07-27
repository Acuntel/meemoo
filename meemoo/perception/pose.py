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

    def __init__(self, model_complexity: int = 1, confidence: float = 0.5) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError(
                "mediapipe not installed — run `uv sync --group perception`"
            ) from exc
        self._mp = mp
        self._pose = mp.solutions.pose.Pose(
            model_complexity=model_complexity,  # 1 = Full (§F.1 recommended)
            min_detection_confidence=confidence,
            min_tracking_confidence=confidence,
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


REACQUIRE_GRACE_S = 3.0  # a track lost longer than this without a re-acquire left
MAX_REACQUIRE_S = 300.0  # hard cap on how long the fallback alone may carry a track


class ReacquiringPose:
    """Primary detector plus a lower-confidence pass for UNACCOUNTED-FOR tracks.

    The miss class this exists for (measured 2026-07-28 on the real suite):
    MediaPipe at confidence 0.5 tracks someone right up to the moment they hit
    the floor and then never re-detects the fallen shape — 0 of 169 post-impact
    frames in cf_s6_fall_left (0 lux) and 0 of 139 in cf_s8_fall_right
    (distant). At confidence 0.15 the same clips recover 86/169 and 84/139.
    A crumpled, half-occluded, badly-lit body is exactly the low-confidence
    case, and it is also exactly the case we must not miss.

    Precision is protected by GATING, not by the threshold: the cheap detector
    only ever runs on a frame the primary already gave up on, and only while
    someone we were tracking is unaccounted for — never on an empty room, and
    never for someone we watched walk out (that is the grace window). So the
    comparison is 'noisy skeleton vs no skeleton at all', never 'noisy skeleton
    vs clean one'. Persistence, the recall engine, needs a position far more
    than it needs a precise one (research 05 §A.4).
    """

    def __init__(
        self,
        primary: PoseEstimator,
        fallback: PoseEstimator,
        grace_s: float = REACQUIRE_GRACE_S,
        max_carry_s: float = MAX_REACQUIRE_S,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._grace_s = grace_s
        self._max_carry_s = max_carry_s
        self._last_seen: float | None = None
        self._carry_since: float | None = None
        self.reacquired_frames = 0

    def infer(self, frame_bgr: Any, t: float) -> PoseFrame:
        frame = self._primary.infer(frame_bgr, t)
        if frame.present:
            self._last_seen = t
            self._carry_since = None
            return frame
        if self._last_seen is None or t - self._last_seen > self._grace_s:
            return frame  # nobody was ever there, or they were seen leaving
        if self._carry_since is not None and t - self._carry_since > self._max_carry_s:
            return frame  # a phantom must not be tracked forever
        retry = self._fallback.infer(frame_bgr, t)
        if not retry.present:
            return frame
        self._last_seen = t
        self._carry_since = self._carry_since if self._carry_since is not None else t
        self.reacquired_frames += 1
        logger.debug("pose re-acquired at low confidence", extra={"fields": {"t": t}})
        return retry

    def close(self) -> None:
        self._primary.close()
        self._fallback.close()


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
