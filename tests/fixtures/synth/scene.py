"""Shared constants for the synthetic clip specs."""

from __future__ import annotations

FLOOR = 0.90
COUCH = 0.80
CHAIR = 0.80
BED = 0.78
OTTOMAN = 0.82
COUCH_ZONE = (0.45, 1.00, 0.74, 0.87)
CHAIR_ZONE = (0.20, 0.42, 0.76, 0.87)
BED_ZONE = (0.35, 0.95, 0.70, 0.85)

FALL = {"candidate": True, "person_down": True, "recovered": False, "escalate": False}
ADL = {"candidate": False, "person_down": False, "recovered": False, "escalate": False}
