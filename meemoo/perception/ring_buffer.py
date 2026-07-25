"""Rolling 60 s skeleton ring buffer + per-event evidence dumps.

Research 05 §A.6: ring-buffer skeletons, not video. ~50 KB/min of JSONL,
privacy-preserving, and the raw material for building an eval set from real
deployments. On every candidate event the buffer is dumped alongside an
optional thumbnail; the dashboard timeline links to these.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from meemoo.perception.landmarks_io import write_clip
from meemoo.perception.types import PoseFrame

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_S = 60.0


class SkeletonRingBuffer:
    """Keeps the last N seconds of pose frames; dumps JSONL evidence on demand."""

    def __init__(self, window_s: float = DEFAULT_WINDOW_S) -> None:
        self._window_s = window_s
        self._frames: deque[PoseFrame] = deque()

    def __len__(self) -> int:
        return len(self._frames)

    def append(self, frame: PoseFrame) -> None:
        self._frames.append(frame)
        while self._frames and frame.t - self._frames[0].t > self._window_s:
            self._frames.popleft()

    def snapshot(self) -> list[PoseFrame]:
        return list(self._frames)

    def dump(
        self,
        out_dir: Path,
        reason: str,
        extra_header: dict[str, Any] | None = None,
        thumbnail_bgr: Any | None = None,
    ) -> Path:
        """Write the buffered skeleton window (and thumbnail) for one event.

        Returns the event directory. Never raises on thumbnail problems —
        evidence writing must not take down the pipeline.
        """
        event_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        event_dir = out_dir / event_id
        event_dir.mkdir(parents=True, exist_ok=True)
        header: dict[str, Any] = {
            "clip": event_id,
            "source": "ring_buffer",
            "reason": reason,
            "window_s": self._window_s,
            **(extra_header or {}),
        }
        n = write_clip(event_dir / "skeleton.jsonl", header, self._frames)
        if thumbnail_bgr is not None:
            self._write_thumbnail(event_dir / "thumbnail.jpg", thumbnail_bgr)
        logger.info(
            "evidence dumped",
            extra={"fields": {"event_dir": str(event_dir), "frames": n, "reason": reason}},
        )
        return event_dir

    @staticmethod
    def _write_thumbnail(path: Path, frame_bgr: Any) -> None:
        try:
            import cv2

            cv2.imwrite(str(path), frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        except ImportError:
            logger.debug("cv2 unavailable; skipping thumbnail")
        except (OSError, ValueError) as exc:
            logger.warning("thumbnail write failed: %s", exc)
