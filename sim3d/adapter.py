"""Blimp3DAdapter — the 2D docking-controller contract over MuJoCo state.

The DockingController consumes only telemetry dataclasses (Pose,
RelativePose, CaptureTelemetry) and emits a ThrustCommand — it was never
entangled with the 2D sim internals, so the controller runs UNMODIFIED
here. This adapter reproduces, against MuJoCo state, exactly what the 2D
rig provides:

- coarse room pose with sigma-5 cm noise,
- the 20 Hz dock camera (same noise, FOV cone, tracking age — the camera
  loses the nose once it is past the mouth plane, as in 2D),
- two-signal capture telemetry (charge-ring continuity + hall/reed seat),
- ~100 ms base-station -> aircraft command latency,
- the hover-duty netBuoyancy estimate.

The only controller input that differs from the 2D defaults is
PhysicsConfig.nose_arm_m: the 3D vehicle's probe reaches 0.585 m from
center (forced by the assigned cone geometry — see sim3d/spec.py). That is
vehicle geometry the real base station would know, not a tuning knob.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from meemoo.flight.constants import DockConfig, PhysicsConfig
from meemoo.flight.floorplan import DockPose
from meemoo.flight.types import CaptureTelemetry, Pose, RelativePose, ThrustCommand
from sim3d.spec import Rig3DConfig
from sim3d.world import MjWorld


def controller_physics_config(rig: Rig3DConfig) -> PhysicsConfig:
    """The 2D PhysicsConfig handed to the controller: stock numbers (what we
    BELIEVE about the vehicle) with only the true probe geometry corrected.
    The engine's own added mass (~half our constant) stays a blind spot on
    purpose — model error is part of what this rig tests."""
    return replace(PhysicsConfig(), nose_arm_m=rig.tip_reach)


def dock_pose(rig: Rig3DConfig) -> DockPose:
    return DockPose(x=0.0, y=0.0, z=rig.dock_z, heading_rad=0.0)


@dataclass(slots=True)
class _Delayed:
    apply_at: float
    cmd: ThrustCommand


class Blimp3DAdapter:
    """Telemetry/command surface the docking controller plugs into."""

    def __init__(
        self,
        world: MjWorld,
        *,
        seed: int = 0,
        dock_cfg: DockConfig | None = None,
        pose_noise_m: float = 0.05,
    ) -> None:
        self.world = world
        self.dcfg = dock_cfg or DockConfig()
        self._pose_rng = random.Random(seed ^ 0xA11CE)
        self._cam_rng = random.Random(seed ^ 0x5EED)
        self._pose_noise = pose_noise_m
        self._queue: list[_Delayed] = []
        self._cam_cache: RelativePose | None = None
        self._cam_last_t = -1.0

    # ------------------------------------------------------------- telemetry
    def pose(self) -> Pose:
        w = self.world
        rot = w.rotation()
        wv, v = w.velocity()
        heading = math.atan2(float(rot[1, 0]), float(rot[0, 0]))
        swing = math.asin(max(-1.0, min(1.0, float(rot[2, 0]))))
        w_body = rot.T @ wv
        n = self._pose_noise

        def jitter() -> float:
            return self._pose_rng.gauss(0.0, n) if n > 0 else 0.0

        x, y, z = w.center_pos
        return Pose(
            x=x + jitter(), y=y + jitter(), z=z + jitter(),
            heading_rad=heading,
            vx=float(v[0]), vy=float(v[1]), vz=float(v[2]),
            yaw_rate=float(wv[2]),
            swing_rad=swing, swing_rate=-float(w_body[1]),
            t=w.t,
        )

    def observe(self) -> RelativePose:
        """The dock camera, mirroring SimulatedDock.observe field for field."""
        cfg, w = self.dcfg, self.world
        period = 1.0 / cfg.camera_rate_hz
        if self._cam_cache is not None and w.t - self._cam_last_t < period:
            c = self._cam_cache
            return RelativePose(
                c.lateral_error_mm, c.vertical_error_mm, c.range_to_throat_mm,
                c.yaw_error_deg, c.tracking_valid, (w.t - self._cam_last_t) * 1000.0,
            )
        tx, ty, tz = w.tip_pos
        rng_axis = tx  # dock axis = +x, mouth plane at x=0
        lateral = ty
        vertical = tz - w.cfg.dock_z
        in_fov = 0.0 <= rng_axis <= cfg.camera_range_m and (
            math.hypot(lateral, vertical)
            <= max(0.10, rng_axis * math.tan(math.radians(cfg.camera_fov_half_deg)))
        )
        rot = w.rotation()
        heading = math.atan2(float(rot[1, 0]), float(rot[0, 0]))
        yaw_err = math.degrees(heading - math.pi)
        yaw_err = (yaw_err + 180.0) % 360.0 - 180.0
        r = self._cam_rng
        self._cam_cache = RelativePose(
            lateral_error_mm=(lateral + r.gauss(0.0, cfg.noise_lateral_m)) * 1000.0,
            vertical_error_mm=(vertical + r.gauss(0.0, cfg.noise_lateral_m)) * 1000.0,
            range_to_throat_mm=max(0.0, rng_axis + r.gauss(0.0, cfg.noise_range_m))
            * 1000.0,
            yaw_error_deg=yaw_err,
            tracking_valid=in_fov,
            tracking_age_ms=0.0,
        )
        self._cam_last_t = w.t
        return self._cam_cache

    def capture(self) -> CaptureTelemetry:
        w = self.world
        dist = w.tip_throat_dist
        return CaptureTelemetry(
            retention_engaged=w.welded,
            contact_continuity=w.tip_plate_contact or dist < w.cfg.continuity_m,
            capture_switch=dist < w.cfg.seat_m,
        )

    @property
    def net_buoyancy_est_gf(self) -> float:
        return self.world.net_buoyancy_est_gf

    # -------------------------------------------------------------- commands
    def command(self, cmd: ThrustCommand) -> None:
        """Queue a base-station command; applies after the radio latency."""
        self._queue.append(_Delayed(
            self.world.t + self.world.cfg.command_latency_s,
            ThrustCommand(cmd.forward_gf, cmd.vertical_gf, cmd.yaw_gf),
        ))

    def set_retention(self, on: bool) -> None:
        self.world.set_retention(on)

    def set_charge_enabled(self, on: bool) -> None:
        self.world.charge_enabled = on

    def step(self, dt: float, *,
             external_force_n: tuple[float, float, float] | None = None) -> None:
        """Advance dt, maturing queued commands at their latency deadline."""
        n = max(1, round(dt / self.world.cfg.timestep))
        for _ in range(n):
            self.world.step(self.world.cfg.timestep,
                            external_force_n=external_force_n)
            while self._queue and self._queue[0].apply_at <= self.world.t + 1e-9:
                cmd = self._queue.pop(0).cmd
                self.world.set_motors(cmd.forward_gf, cmd.vertical_gf, cmd.yaw_gf)
