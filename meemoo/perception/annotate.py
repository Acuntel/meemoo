"""Annotated-frame rendering: bbox, skeleton, state label (for /ws/video).

The WebSocket endpoint itself lands in step 07; the pipeline already produces
annotated JPEG frames through a FrameHub so the dashboard's Live View can
attach later without touching perception.
"""

from __future__ import annotations

from typing import Any

from meemoo.perception.types import SKELETON_EDGES, Landmarks

_STATE_COLORS = {
    "UPRIGHT": (80, 200, 80),
    "DESCENDING": (0, 200, 255),
    "SUPPRESSED_FURNITURE": (200, 180, 60),
    "GROUNDED_CANDIDATE": (0, 120, 255),
    "VERIFYING": (0, 60, 255),
    "ESCALATE": (0, 0, 255),
    "SNOOZED": (180, 180, 180),
    "ABSENT": (120, 120, 120),
}


def annotate_frame(
    frame_bgr: Any,
    landmarks: Landmarks | None,
    state_label: str,
    extra_label: str = "",
) -> Any:
    """Draw skeleton + bbox + state banner onto a copy of the frame (needs cv2)."""
    import cv2

    out = frame_bgr.copy()
    h, w = out.shape[:2]
    color = _STATE_COLORS.get(state_label, (255, 255, 255))

    if landmarks is not None:
        pts = [(int(p[0] * w), int(p[1] * h)) for p in landmarks]
        vis = [p[3] > 0.5 for p in landmarks]
        for a, b in SKELETON_EDGES:
            if vis[a] and vis[b]:
                cv2.line(out, pts[a], pts[b], color, 2, cv2.LINE_AA)
        for i, (x, y) in enumerate(pts):
            if vis[i]:
                cv2.circle(out, (x, y), 3, color, -1, cv2.LINE_AA)
        xs = [p[0] for p, v in zip(pts, vis, strict=True) if v]
        ys = [p[1] for p, v in zip(pts, vis, strict=True) if v]
        if xs and ys:
            cv2.rectangle(
                out, (min(xs) - 8, min(ys) - 8), (max(xs) + 8, max(ys) + 8), color, 1
            )

    banner = state_label if not extra_label else f"{state_label}  {extra_label}"
    cv2.rectangle(out, (0, 0), (w, 28), (20, 20, 20), -1)
    cv2.putText(
        out, banner, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA
    )
    return out


def encode_jpeg(frame_bgr: Any, quality: int = 75) -> bytes | None:
    """JPEG-encode a frame; None on failure (never raises into the pipeline)."""
    import cv2

    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return bytes(buf.tobytes()) if ok else None
