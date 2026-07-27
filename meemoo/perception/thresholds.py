"""Fall-detection thresholds, loaded from the committed golden_thresholds.json.

Research 05 §A.3. The JSON file is the single source of truth so that any
tuning shows up as a reviewable diff. The loaded version string is registered
in the version registry (core.versioning) so every escalation-relevant record
says which thresholds were in force. NEVER loosen these to make a test pass —
the sim and the fixtures keep honest physics (Constitution Art. II §4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path

GOLDEN_PATH = Path(__file__).with_name("golden_thresholds.json")


@dataclass(frozen=True, slots=True)
class Thresholds:
    """All fall-state-machine constants (units: degrees, torso-lengths, seconds)."""

    version: str
    # posture
    horizontal_angle_deg: float
    near_floor_elevation: float
    furniture_elevation: float
    # descent (precision signal, NOT required — persistence is the recall engine)
    ballistic_v: float
    ballistic_drop: float
    controlled_max_v: float
    # stillness
    still_motion: float
    purposeful_motion: float
    # timers
    t_settle: float
    t_candidate: float
    t_confirm: float
    t_voice_1: float
    t_voice_2: float
    t_escalate_after_down: float  # measured from person.down, NOT from grounding
    t_longlie: float
    t_recovered: float
    # CANDIDATE_SOFT (deliberate floor-sitters get a gentler, later question)
    t_soft_candidate: float
    t_soft_confirm: float
    # furniture escapes
    furniture_still_escape_s: float
    # recovery
    upright_max_angle_deg: float
    recovered_min_elevation: float
    # VANISHED_DOWN
    vanish_v_window_s: float
    vanish_bottom_y: float


@lru_cache(maxsize=1)
def load_thresholds(path: Path = GOLDEN_PATH) -> Thresholds:
    """Load and cache the golden thresholds file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    names = {f.name for f in fields(Thresholds)}
    kwargs = {k: v for k, v in raw.items() if k in names}
    return Thresholds(**kwargs)
