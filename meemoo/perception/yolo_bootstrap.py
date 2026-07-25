"""Day-one furniture bootstrap via YOLOv8n (COCO) — research 05 §A.2.3.

Runs ONCE at install to seed the rest-zone grid so day-one behaviour isn't
naive; learned evidence outweighs the detector over time. The ultralytics
import and model download are lazy and optional — a missing dependency or
missing weights must never crash anything (Constitution Art. IX §3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from meemoo.perception.calibration import ZoneGrid

logger = logging.getLogger(__name__)

# COCO class names we treat as elevated rest surfaces.
REST_CLASSES = frozenset({"bed", "couch", "chair", "dining table"})


@dataclass(frozen=True, slots=True)
class FurnitureBox:
    """One detected furniture item, image-normalized xyxy."""

    cls_name: str
    x0: float
    y0: float
    x1: float
    y1: float


def seed_zones_from_boxes(grid: ZoneGrid, boxes: list[FurnitureBox]) -> int:
    """Seed the rest-zone grid from detector boxes; returns zones seeded.

    A person resting ON furniture has their support point in the box's lower
    half (seat/mattress surface down to the box bottom), so seed that band.
    """
    seeded = 0
    for box in boxes:
        if box.cls_name not in REST_CLASSES:
            continue
        y_mid = (box.y0 + box.y1) / 2.0
        grid.seed_rect(box.x0, box.x1, y_mid, box.y1)
        seeded += 1
    return seeded


def detect_furniture(frame_bgr: Any, conf: float = 0.35) -> list[FurnitureBox]:
    """Run YOLOv8n on one frame. Returns [] (with a log line) if unavailable."""
    try:
        from ultralytics import YOLO  # heavy, downloads weights on first use
    except ImportError:
        logger.warning(
            "yolo bootstrap unavailable (ultralytics not installed); "
            "zone grid will rely on learned evidence only",
        )
        return []
    try:
        model = YOLO("yolov8n.pt")
        h, w = frame_bgr.shape[:2]
        results = model.predict(frame_bgr, conf=conf, verbose=False)
        boxes: list[FurnitureBox] = []
        for r in results:
            names = r.names
            for b in r.boxes:
                cls_name = str(names[int(b.cls[0])])
                x0, y0, x1, y1 = (float(v) for v in b.xyxy[0])
                boxes.append(
                    FurnitureBox(cls_name, x0 / w, y0 / h, x1 / w, y1 / h)
                )
        return boxes
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("yolo bootstrap failed: %s", exc)
        return []
