"""Procedural 33-landmark body model for synthetic clips.

Postures are templates: landmark index -> (bx, by) in torso units, where bx is
lateral/along-body offset (flipped by ``direction``) and by is HEIGHT ABOVE the
current support surface. Image mapping (y down):

    ix = hip_x + direction * bx * S
    iy = support_level - by * S
"""

from __future__ import annotations

import math
import random

from meemoo.perception.types import N_LANDMARKS

Template = dict[int, tuple[float, float]]

S = 0.17  # torso length in image units at the fixture camera depth
FLOOR_Y = 0.90  # flat floor line (a=0, b=0.90)

STAND: Template = {
    0: (0.0, 3.10),
    11: (-0.28, 2.80),
    12: (0.28, 2.80),
    13: (-0.40, 2.35),
    14: (0.40, 2.35),
    15: (-0.42, 1.90),
    16: (0.42, 1.90),
    23: (-0.16, 1.80),
    24: (0.16, 1.80),
    25: (-0.17, 0.90),
    26: (0.17, 0.90),
    27: (-0.18, 0.00),
    28: (0.18, 0.00),
}

LIE: Template = {  # horizontal, head toward +bx
    0: (1.50, 0.30),
    11: (1.00, 0.30),
    12: (1.00, 0.10),
    13: (0.70, 0.35),
    14: (0.70, 0.05),
    15: (0.50, 0.30),
    16: (0.50, 0.02),
    23: (-0.08, 0.25),
    24: (0.08, 0.08),
    25: (-0.85, 0.25),
    26: (-0.85, 0.10),
    27: (-1.60, 0.20),
    28: (-1.60, 0.05),
}

SIT_CHAIR: Template = {  # sitting on an elevated seat, torso upright
    0: (0.0, 1.35),
    11: (-0.28, 1.05),
    12: (0.28, 1.05),
    13: (-0.36, 0.70),
    14: (0.36, 0.70),
    15: (-0.30, 0.35),
    16: (0.30, 0.35),
    23: (-0.16, 0.05),
    24: (0.16, 0.05),
    25: (-0.20, -0.10),
    26: (0.20, -0.10),
    27: (-0.20, -0.55),
    28: (0.20, -0.55),
}

SEATED_FLOOR: Template = {  # on the floor, torso ~30 deg from vertical
    0: (0.75, 1.25),
    11: (0.36, 0.99),
    12: (0.64, 0.95),
    13: (0.55, 0.65),
    14: (0.75, 0.60),
    15: (0.60, 0.35),
    16: (0.85, 0.30),
    23: (-0.14, 0.10),
    24: (0.14, 0.10),
    25: (0.55, 0.30),
    26: (0.65, 0.15),
    27: (1.00, 0.10),
    28: (1.10, 0.05),
}

BEND: Template = {  # bending over to pick something up; hips stay high
    0: (0.95, 1.20),
    11: (0.70, 1.40),
    12: (0.80, 1.30),
    13: (0.85, 1.00),
    14: (0.95, 0.95),
    15: (0.90, 0.65),
    16: (1.00, 0.60),
    23: (-0.16, 1.75),
    24: (0.16, 1.75),
    25: (-0.17, 0.90),
    26: (0.17, 0.90),
    27: (-0.18, 0.00),
    28: (0.18, 0.00),
}

_KEY_IDS = sorted(STAND.keys())


def blend(a: Template, b: Template, u: float) -> Template:
    return {
        i: (a[i][0] + (b[i][0] - a[i][0]) * u, a[i][1] + (b[i][1] - a[i][1]) * u)
        for i in _KEY_IDS
    }


def _derive_all(key_pts: dict[int, tuple[float, float]]) -> list[list[float]]:
    """Fill all 33 landmarks (image coords) from the 13 key points."""
    pts: dict[int, tuple[float, float]] = dict(key_pts)
    nose = pts[0]
    for i in range(1, 11):  # face cluster around the nose
        pts[i] = (nose[0] + 0.03 * ((i % 3) - 1), nose[1] + 0.02 * ((i % 4) - 1.5))
    for wrist, ids in ((15, (17, 19, 21)), (16, (18, 20, 22))):
        wx, wy = pts[wrist]
        for k, i in enumerate(ids):
            pts[i] = (wx + 0.012 * (k + 1), wy + 0.008 * k)
    for ankle, foot_ids in ((27, (29, 31)), (28, (30, 32))):
        ax, ay = pts[ankle]
        for k, i in enumerate(foot_ids):
            pts[i] = (ax + 0.015 * (k + 1), ay + 0.005)
    return [[pts[i][0], pts[i][1], 0.0, 1.0] for i in range(N_LANDMARKS)]


def make_frame(
    template: Template,
    hip_x: float,
    support_level: float,
    direction: int,
    rng: random.Random,
    t: float,
    jitter: float = 0.0015,
    vis_base: float = 0.95,
    vis_sigma: float = 0.02,
    swing: float = 0.0,
    sway: float = 0.0,
    occlude_legs: bool = False,
) -> list[list[float]]:
    """One frame of landmarks with noise, breathing, gait swing, and sway."""
    breathe = 0.001 * math.sin(2.0 * math.pi * 0.25 * t)
    key_pts: dict[int, tuple[float, float]] = {}
    for i in _KEY_IDS:
        bx, by = template[i]
        if swing > 0.0 and i in (15, 16, 25, 26, 27, 28):  # gait swing
            phase = 0.0 if i % 2 else math.pi
            bx += swing * math.sin(2.0 * math.pi * 1.5 * t + phase)
        ix = hip_x + direction * bx * S + rng.gauss(0.0, jitter)
        iy = support_level - by * S + rng.gauss(0.0, jitter)
        if i <= 16:  # breathing moves the chest/head, not the whole skeleton
            iy += breathe
        if sway > 0.0:  # purposeful whole-body movement (yoga etc.)
            ix += sway * math.sin(2.0 * math.pi * 0.5 * t)
            iy += 0.5 * sway * math.sin(2.0 * math.pi * 0.4 * t + 1.0)
        key_pts[i] = (ix, iy)
    lm = _derive_all(key_pts)
    for i in range(N_LANDMARKS):
        vis = min(1.0, max(0.0, rng.gauss(vis_base, vis_sigma)))
        if occlude_legs and i >= 25:
            vis = min(vis, rng.gauss(0.2, 0.05))
        lm[i][3] = round(vis, 2)
    return lm
