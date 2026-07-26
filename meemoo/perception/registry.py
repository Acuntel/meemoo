"""Process-wide handle to the running PerceptionPipeline (registry pattern).

/ws/video consumes the pipeline's FrameHub — but api/ must not construct
perception internals (Art. II §2). Whoever wires the app registers the
pipeline here; with none registered (headless dev, no cv2) the endpoint
reports ``ready: False`` and nothing crashes (Art. IX §3).
"""

from __future__ import annotations

from meemoo.perception.pipeline import PerceptionPipeline

_active: PerceptionPipeline | None = None


def set_active_pipeline(pipeline: PerceptionPipeline | None) -> None:
    """Register (or clear) the running perception pipeline for API access."""
    global _active
    _active = pipeline


def get_active_pipeline() -> PerceptionPipeline | None:
    return _active
