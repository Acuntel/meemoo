"""Shared perception datatypes and landmark conventions.

Landmark frames follow the MediaPipe Pose 33-landmark layout: each landmark is
``[x, y, z, visibility]`` with x/y normalized to image size and **y pointing
DOWN** (image convention — the floor is at LARGE y). All derived signals are
torso-length-normalized (research 05 §A.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

# MediaPipe Pose landmark indices used by the signal pipeline.
NOSE: Final = 0
L_SHOULDER: Final = 11
R_SHOULDER: Final = 12
L_ELBOW: Final = 13
R_ELBOW: Final = 14
L_WRIST: Final = 15
R_WRIST: Final = 16
L_HIP: Final = 23
R_HIP: Final = 24
L_KNEE: Final = 25
R_KNEE: Final = 26
L_ANKLE: Final = 27
R_ANKLE: Final = 28
N_LANDMARKS: Final = 33

SUPPORT_LANDMARKS: Final = (L_HIP, R_HIP, L_SHOULDER, R_SHOULDER, L_KNEE, R_KNEE)

# Skeleton edges for annotation (subset of MediaPipe POSE_CONNECTIONS).
SKELETON_EDGES: Final[tuple[tuple[int, int], ...]] = (
    (L_SHOULDER, R_SHOULDER),
    (L_SHOULDER, L_ELBOW),
    (L_ELBOW, L_WRIST),
    (R_SHOULDER, R_ELBOW),
    (R_ELBOW, R_WRIST),
    (L_SHOULDER, L_HIP),
    (R_SHOULDER, R_HIP),
    (L_HIP, R_HIP),
    (L_HIP, L_KNEE),
    (L_KNEE, L_ANKLE),
    (R_HIP, R_KNEE),
    (R_KNEE, R_ANKLE),
)

Landmarks = list[list[float]]  # 33 x [x, y, z, visibility]


@dataclass(frozen=True, slots=True)
class PoseFrame:
    """One pose-estimation result. ``landmarks is None`` == no person found."""

    t: float  # seconds; clip time for playback, monotonic time live
    landmarks: Landmarks | None

    @property
    def present(self) -> bool:
        return self.landmarks is not None


@dataclass(frozen=True, slots=True)
class SignalFrame:
    """Torso-length-normalized signals for one frame (research 05 §A.1)."""

    t: float
    present: bool
    x: float  # mid-hip x, image-normalized
    hip_y: float  # mid-hip y, image-normalized (y down)
    torso_angle: float  # degrees from image vertical; >55 = horizontal-ish
    support_y: float  # lowest (max-y) visible hip/shoulder/knee point
    elevation: float  # height above calibrated floor line, in torso-lengths
    v_descent: float  # torso-lengths/sec, positive = moving DOWN
    motion_energy: float  # torso-lengths/sec, windowed-median filtered
    vis_frac: float  # fraction of landmarks with visibility > 0.5
    aspect: float  # pose bbox height/width
    scale: float  # S — running-median torso length (image units)

    @staticmethod
    def absent(t: float) -> SignalFrame:
        return SignalFrame(
            t=t,
            present=False,
            x=0.0,
            hip_y=0.0,
            torso_angle=0.0,
            support_y=0.0,
            elevation=0.0,
            v_descent=0.0,
            motion_energy=0.0,
            vis_frac=0.0,
            aspect=0.0,
            scale=0.0,
        )


class FloorOracle(Protocol):
    """Answers 'where is the floor at image column x?' (research 05 §A.2)."""

    @property
    def fitted(self) -> bool: ...

    def floor_y(self, x: float) -> float: ...


class RestZoneOracle(Protocol):
    """Answers 'is (x, support_y) a learned bed/couch/chair zone?'."""

    def is_rest_zone(self, x: float, y: float) -> bool: ...
