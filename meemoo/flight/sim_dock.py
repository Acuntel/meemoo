"""SimulatedDock — the dock is its own device (Constitution Art. II §3).

Implements the research/06 §B–§D chain honestly:
- FUNNEL: capture succeeds iff |radial error| < R_capture at mouth contact
  AND axial speed < v_max; otherwise the blimp BOUNCES off (restitution).
- A funnel does NOT passively centre a neutrally buoyant vehicle: progress
  down the cone requires HELD FORWARD THRUST (min_slide_thrust_gf). Drop the
  thrust mid-slide and the nose stalls, then slides back out.
- MAGNET: the dock-side electromagnet can only seat the final centimetre
  (progress ≥ magnet_seat_progress). Cutting current leaves a small
  remanence force unless the reverse pulse runs.
- TWO-SIGNAL CAPTURE: contact continuity (charge rings) AND the hall/reed
  switch. ``CaptureTelemetry.confirmed`` requires both — never vision, never
  a single channel.
- CHARGING through the concentric rings; load cell reads trim; helium level
  decays and ``top_off()`` restores it (Art. VII §5 — the physical
  subscription's telemetry lives in v1).
"""

from __future__ import annotations

import logging
import math
import random

from meemoo.flight.constants import DockConfig
from meemoo.flight.controller import DockController
from meemoo.flight.floorplan import DockPose
from meemoo.flight.physics import BlimpPhysics
from meemoo.flight.types import CaptureTelemetry, ChargeTelemetry, RelativePose

logger = logging.getLogger(__name__)


class SimulatedDock(DockController):
    """Dock-side device model. Base station is wired to it; blimp is not."""

    def __init__(
        self,
        pose: DockPose,
        config: DockConfig | None = None,
        *,
        seed: int = 0,
    ) -> None:
        self.pose = pose
        self.cfg = config or DockConfig()
        self.rng = random.Random(seed ^ 0x5EED)
        self.retention_commanded = False
        self.retention_engaged = False
        self.charge_enabled = False
        self.helium_level_pct = 100.0
        self.load_cell_g = 0.0
        # funnel progress: 0 = mouth, 1 = fully seated at throat
        self.progress = 0.0
        self.in_funnel = False
        self.seated = False
        self.last_rejected: str | None = None  # why the last contact bounced
        self._remanence_until = -1.0
        self._camera_last_t = -1.0
        self._camera_cache: RelativePose | None = None
        self._now = 0.0
        self._battery_pct_hint = 0.0  # last battery seen by interact()
        self._prev_rng_axis: float | None = None  # nose range last step

    # ---------------------------------------------------- DockController API
    def set_retention(self, on: bool) -> None:
        """Electromagnet on/off. Off runs the reverse demagnetising pulse
        after a brief remanence window (research/06 §B release)."""
        if self.retention_commanded and not on:
            self._remanence_until = self._now + 0.5  # pulse clears it after 0.5 s
        self.retention_commanded = on

    def set_charge_enabled(self, on: bool) -> None:
        self.charge_enabled = on

    def capture(self) -> CaptureTelemetry:
        return CaptureTelemetry(
            retention_engaged=self.retention_engaged,
            contact_continuity=self.progress >= self.cfg.contact_progress,
            capture_switch=self.seated,
        )

    def charge(self, battery_pct: float) -> ChargeTelemetry:
        charging = self.charge_enabled and self.capture().confirmed
        if not charging:
            state = "none"
            current = 0.0
        elif battery_pct >= 99.9:
            state, current = "complete", 15.0
        elif battery_pct >= 80.0:
            state, current = "topping", 120.0
        else:
            state, current = "bulk", 250.0
        return ChargeTelemetry(
            charge_current_ma=current,
            pack_voltage_mv=3500.0 + 700.0 * battery_pct / 100.0,
            pack_temp_c=24.0 + (3.0 if state == "bulk" else 0.5),
            charge_state=state,
        )

    def charge_telemetry(self) -> ChargeTelemetry:
        """DockController API: charge state at the last-seen battery level."""
        return self.charge(self._battery_pct_hint)

    def top_off(self) -> None:
        """Helium top-off (the dock-integrated cartridge, simulated)."""
        self.helium_level_pct = 100.0
        logger.info("dock: helium topped off")

    def force_capture(self, phys: BlimpPhysics) -> None:
        """Start an episode already seated on the dock (both signals true)."""
        self.in_funnel = True
        self.progress = 1.0
        self.seated = True
        self.retention_commanded = True
        self.retention_engaged = True
        ax, ay = self.pose.axis
        arm = phys.cfg.nose_arm_m
        phys.heading = math.atan2(-ay, -ax)
        nx = self.pose.x - ax * self.cfg.throat_depth_m
        ny = self.pose.y - ay * self.cfg.throat_depth_m
        phys.x = nx - arm * math.cos(phys.heading)
        phys.y = ny - arm * math.sin(phys.heading)
        phys.z = self.pose.z
        phys.vx = phys.vy = phys.vz = 0.0
        phys.swing = phys.swing_rate = 0.0
        phys.frozen = True

    # ------------------------------------------------------------ dock camera
    def observe(self, phys: BlimpPhysics) -> RelativePose:
        """Relative pose from the dock camera looking OUT along the approach
        corridor (research/06 §A) — 20 Hz, noisy, with tracking age."""
        cfg = self.cfg
        period = 1.0 / cfg.camera_rate_hz
        if self._camera_cache is not None and phys.t - self._camera_last_t < period:
            age = (phys.t - self._camera_last_t) * 1000.0
            c = self._camera_cache
            return RelativePose(
                c.lateral_error_mm, c.vertical_error_mm, c.range_to_throat_mm,
                c.yaw_error_deg, c.tracking_valid, age,
            )
        nx, ny, nz = phys.nose_position()
        ax, ay = self.pose.axis
        dx, dy = nx - self.pose.x, ny - self.pose.y
        rng_axis = dx * ax + dy * ay  # distance out along the approach axis
        lateral = -dx * ay + dy * ax  # signed cross-axis offset
        vertical = nz - self.pose.z
        in_fov = 0.0 <= rng_axis <= cfg.camera_range_m and (
            math.hypot(lateral, vertical)
            <= max(0.10, rng_axis * math.tan(math.radians(cfg.camera_fov_half_deg)))
        )
        approach_heading = math.atan2(-ay, -ax)  # facing INTO the mouth
        yaw_err = math.degrees(phys.heading - approach_heading)
        yaw_err = (yaw_err + 180.0) % 360.0 - 180.0
        n_lat = self.rng.gauss(0.0, cfg.noise_lateral_m)
        n_ver = self.rng.gauss(0.0, cfg.noise_lateral_m)
        n_rng = self.rng.gauss(0.0, cfg.noise_range_m)
        self._camera_cache = RelativePose(
            lateral_error_mm=(lateral + n_lat) * 1000.0,
            vertical_error_mm=(vertical + n_ver) * 1000.0,
            range_to_throat_mm=max(0.0, rng_axis + n_rng) * 1000.0,
            yaw_error_deg=yaw_err,
            tracking_valid=in_fov,
            tracking_age_ms=0.0,
        )
        self._camera_last_t = phys.t
        return self._camera_cache

    # -------------------------------------------------------- funnel contact
    def interact(self, phys: BlimpPhysics, dt: float) -> None:
        """Funnel/magnet mechanics, called every physics step."""
        self._now = phys.t
        cfg = self.cfg
        self._battery_pct_hint = phys.battery_pct
        self._update_helium(phys, dt)
        if phys.frozen:
            self._while_captured(phys)
            return

        nx, ny, nz = phys.nose_position()
        ax, ay = self.pose.axis
        rng_axis = (nx - self.pose.x) * ax + (ny - self.pose.y) * ay
        lateral = -(nx - self.pose.x) * ay + (ny - self.pose.y) * ax
        vertical = nz - self.pose.z
        radial = math.hypot(lateral, vertical)
        v_axis = -(phys.vx * ax + phys.vy * ay)  # positive = moving INTO the dock

        if not self.in_funnel:
            self.progress = 0.0
            self.seated = False
            prev = self._prev_rng_axis
            self._prev_rng_axis = rng_axis
            # crossing the mouth plane this step (no tunnelling through the
            # dock face — the sim tells the truth, Art. II §4)
            crossed = prev is not None and prev > 0.0 and rng_axis <= 0.0 and v_axis > 0.0
            if crossed and radial < 0.35:
                # nose reached the mouth plane — the capture test (§G.4)
                if radial >= cfg.r_capture_m:
                    self._bounce(phys, ax, ay, v_axis, "radial_error")
                elif v_axis > cfg.v_max_capture_mps:
                    self._bounce(phys, ax, ay, v_axis, "too_fast")
                else:
                    self.in_funnel = True
                    # entry means the nose is physically a couple of cm past
                    # the lip — grace against ejection while the held-thrust
                    # command is still in the 100 ms radio pipe
                    self.progress = 0.02
                    self.last_rejected = None
            return

        # in the funnel: held thrust slides the nose to the throat
        thrust_gf = phys.applied.forward_gf
        if thrust_gf >= cfg.min_slide_thrust_gf:
            slide_v = min(0.06, max(0.01, v_axis if v_axis > 0 else 0.02))
            self.progress += (slide_v / cfg.throat_depth_m) * dt
        else:
            self.progress -= cfg.slide_backout_rate * dt  # stalled: drifts back out
        # magnet seats the last centimetre once close enough
        magnet_force = self.retention_commanded or (
            phys.t < self._remanence_until and cfg.remanence_gf > 0.0
        )
        if magnet_force and self.progress >= cfg.magnet_seat_progress:
            self.progress = min(1.0, self.progress + 2.0 * dt)
        self.progress = min(1.0, self.progress)
        if self.progress <= 0.0:
            self.in_funnel = False  # slid back out of the mouth
            self.progress = 0.0
            return
        # while in the cone the wall constrains the airframe to the axis
        wall_r = cfg.r_capture_m * (1.0 - self.progress) + cfg.r_throat_m * self.progress
        self._constrain_to_cone(phys, wall_r)
        self.seated = self.progress >= cfg.switch_progress
        self.retention_engaged = self.retention_commanded and self.seated
        if self.retention_engaged and self.capture().confirmed:
            # magnet holds the shell; the dock now carries the airframe
            phys.frozen = True
            logger.info("dock: captured — two-signal confirmed")

    def _while_captured(self, phys: BlimpPhysics) -> None:
        """Held by the magnet: charge + load-cell trim reading."""
        self.retention_engaged = self.retention_commanded
        self.load_cell_g = -phys.net_buoyancy_true_gf  # heavy → positive grams
        if not self.retention_commanded and phys.t >= self._remanence_until:
            phys.frozen = False  # released (reverse pulse done)
            self.seated = False
            self.in_funnel = False
            self.progress = 0.0

    def _bounce(self, phys: BlimpPhysics, ax: float, ay: float, v_axis: float,
                reason: str) -> None:
        e = self.cfg.bounce_restitution
        phys.vx += ax * v_axis * (1.0 + e)
        phys.vy += ay * v_axis * (1.0 + e)
        phys.vz += self.rng.uniform(-0.02, 0.02)
        self.last_rejected = reason
        logger.debug("dock: bounce (%s)", reason)

    def _constrain_to_cone(self, phys: BlimpPhysics, wall_r: float) -> None:
        cfg = self.cfg
        ax, ay = self.pose.axis
        nose_depth = cfg.throat_depth_m * self.progress
        nx = self.pose.x - ax * nose_depth
        ny = self.pose.y - ay * nose_depth
        arm = phys.cfg.nose_arm_m
        phys.x = nx - arm * math.cos(phys.heading)
        phys.y = ny - arm * math.sin(phys.heading)
        # cone wall clamps vertical error to the local radius
        dz = phys.z - self.pose.z
        if abs(dz) > wall_r:
            phys.z = self.pose.z + math.copysign(wall_r, dz)
            phys.vz = 0.0
        phys.vx *= 0.5
        phys.vy *= 0.5

    def _update_helium(self, phys: BlimpPhysics, dt: float) -> None:
        decay = self.cfg.helium_decay_pct_per_day * dt / 86400.0
        self.helium_level_pct = max(0.0, self.helium_level_pct - decay)
        phys._buoyancy_extra_gf = -(100.0 - self.helium_level_pct) * self.cfg.helium_gf_per_pct
