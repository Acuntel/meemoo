"""VideoSource interface: `webcam` | `mjpeg_url` | `file` behind one contract.

This is the future-hardware swap point (step-02 §1): the ESP32-CAM on the
blimp will arrive as an `mjpeg_url` source and NOTHING downstream changes.
Keep it pure — no perception logic in here.

cv2 is imported lazily so the package imports (and the whole test suite runs)
without OpenCV installed. Install the `perception` dependency group for live
video: ``uv sync --group perception``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from meemoo.core.config import Settings

logger = logging.getLogger(__name__)


class VideoSourceError(RuntimeError):
    """A video source could not be opened or configured."""


class VideoSource(Protocol):
    """Minimal contract every frame producer satisfies."""

    @property
    def fps(self) -> float: ...

    def read(self) -> Any | None:
        """Next BGR frame (numpy array), or None when the source is exhausted."""
        ...

    def close(self) -> None: ...


def _require_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:  # degrade with a clear message, never at import
        raise VideoSourceError(
            "OpenCV not installed — run `uv sync --group perception`"
        ) from exc
    return cv2


class _CaptureSource:
    """Shared cv2.VideoCapture wrapper for webcam/MJPEG/file."""

    def __init__(self, target: int | str, fps_fallback: float, loop: bool = False) -> None:
        cv2 = _require_cv2()
        self._cap = cv2.VideoCapture(target)
        if not self._cap.isOpened():
            raise VideoSourceError(f"could not open video source {target!r}")
        self._loop = loop
        self._target = target
        reported = float(self._cap.get(cv2.CAP_PROP_FPS) or 0.0)
        self._fps = reported if 1.0 <= reported <= 120.0 else fps_fallback

    @property
    def fps(self) -> float:
        return self._fps

    def read(self) -> Any | None:
        ok, frame = self._cap.read()
        if ok:
            return frame
        if self._loop:
            self._cap.set(_require_cv2().CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if ok:
                return frame
        return None

    def close(self) -> None:
        self._cap.release()


class WebcamSource(_CaptureSource):
    def __init__(self, index: int = 0) -> None:
        super().__init__(index, fps_fallback=30.0)


class MjpegUrlSource(_CaptureSource):
    """MJPEG-over-HTTP stream — the future blimp-camera transport."""

    def __init__(self, url: str) -> None:
        super().__init__(url, fps_fallback=15.0)


class FileSource(_CaptureSource):
    """Recorded clip playback for testing; validates the path eagerly."""

    def __init__(self, path: str, loop: bool = False) -> None:
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"video file not found: {resolved}")
        super().__init__(str(resolved), fps_fallback=30.0, loop=loop)


def open_source(settings: Settings) -> VideoSource:
    """Build the configured VideoSource from settings (VIDEO_SOURCE et al.)."""
    kind = settings.video_source
    if kind == "webcam":
        return WebcamSource(0)
    if kind == "mjpeg_url":
        if not settings.video_url:
            raise VideoSourceError("video_source=mjpeg_url requires VIDEO_URL")
        return MjpegUrlSource(settings.video_url)
    if kind == "file":
        if not settings.video_file:
            raise VideoSourceError("video_source=file requires VIDEO_FILE")
        return FileSource(settings.video_file)
    raise VideoSourceError(f"unknown video source kind: {kind!r}")


def to_gate_gray(frame_bgr: Any, width: int = 160, height: int = 120) -> bytes:
    """Downscale a BGR frame to the motion gate's tiny grayscale bytes."""
    cv2 = _require_cv2()
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)
    return bytes(small.tobytes())
