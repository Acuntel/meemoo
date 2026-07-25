"""VideoSource contract tests that need no OpenCV (cv2 paths are lazy)."""

from __future__ import annotations

import pytest

from meemoo.core.config import Settings
from meemoo.perception.video import FileSource, VideoSourceError, open_source


def test_file_source_missing_path_fails_fast() -> None:
    with pytest.raises(FileNotFoundError):
        FileSource("/nonexistent/clip.mp4")


def test_open_source_file_requires_video_file(bare_settings: Settings) -> None:
    settings = bare_settings.model_copy(update={"video_source": "file", "video_file": None})
    with pytest.raises(VideoSourceError):
        open_source(settings)


def test_open_source_mjpeg_requires_url(bare_settings: Settings) -> None:
    settings = bare_settings.model_copy(update={"video_source": "mjpeg_url", "video_url": None})
    with pytest.raises(VideoSourceError):
        open_source(settings)


def test_missing_cv2_never_crashes_import() -> None:
    """The perception package must import without OpenCV (Art. IX §3)."""
    import meemoo.perception.pipeline  # noqa: F401
    import meemoo.perception.video  # noqa: F401
