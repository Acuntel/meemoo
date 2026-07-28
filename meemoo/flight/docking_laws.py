"""The moving legs of the docking machine: final approach and capture.

The machine (phases, retries, timeouts) lives in docking.py; station
keeping lives in dock_hover.py; the commit decision lives in dock_plan.py
and the in-funnel gates in dock_slide.py. What is left here is the part
that MOVES: the approach leg and the slide onto the magnet.

Everything is measured against honest physics (Art. II §4) and the
comments record the measured failure modes that shaped each law — v1
scored 16% first-attempt in 2D and 7% in MuJoCo, and every rule here
exists because one of those runs said so.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from meemoo.flight.dock_hover import HoverLaws
from meemoo.flight.types import (
    CaptureTelemetry,
    DockPhase,
    Pose,
    RelativePose,
    ThrustCommand,
    wrap_angle,
)

if TYPE_CHECKING:
    from meemoo.flight.docking import _AxisErrors


_TRACKING_STALE_MS = 400.0  # PLD_BTOUT analogue


class ApproachLaws(HoverLaws):
    """Mixin: the approach leg + capture slide. State lives on the
    controller; :class:`HoverLaws` carries the station-keeping half."""

    def _approach(self, pose: Pose, err: _AxisErrors, dt: float) -> ThrustCommand:
        """Plan the last metre; fly it. The planner (dock_plan.py) owns the
        commit decision, so a bad line HOLDS instead of going around."""
        # A stale camera close-in is the classic crash — but a go-around is a
        # 25 s punishment for a tracking flicker. Hold the corridor and
        # re-acquire; only a LONG loss is worth the retreat.
        #
        # The camera legitimately loses the nose in the last 25 cm (it looks
        # OUT along the corridor), so that band is exempt — but PAST the
        # mouth plane is not the same as at it. Exempting everything below
        # 0.25 m including NEGATIVE range let a nose that sailed past the
        # dock off-axis go blind and simply sit there until the phase
        # timeout: it cost 186 of 200 episodes their first attempt.
        self._stale_t = 0.0 if err.fresh else self._stale_t + dt
        near_mouth = 0.0 <= err.range_m <= 0.25
        if self._stale_t > 20.0 and not near_mouth:
            self._abort("camera_lost")
            return ThrustCommand()
        if err.range_m > 0.25:
            self._no_reenter = False  # cleared once we are back out on final
        # The mouth is at lateral ≈ 0: reaching the mouth PLANE 20 cm off
        # axis is flying past the dock, not docking with it.
        at_mouth = 0.0 <= err.range_m < 0.12 and abs(err.lateral_m) < 0.18
        # blind, or past the plane without a capture: hold — which means fly
        # back out to the corridor and re-plan, never press on into the face
        blind = (self._stale_t > 0.7 and not near_mouth) or (
            err.range_m < 0.0 and not at_mouth
        )
        est = self.draft.estimate
        plan = self.planner.update(
            err, est.lateral_gf(self._axis), dt, force_hold=blind
        )
        if plan.replanned:
            self.replans += 1
        if plan.abort is not None:
            self._abort(plan.abort)
            return ThrustCommand()
        if at_mouth and not self._no_reenter:
            self.slide.reset(err)
            self._enter(DockPhase.CAPTURE_PENDING)
        elif plan.hold:
            # Lost the nose? BACK OFF, do not go around. The dock camera
            # looks out along the corridor through a cone, so its usable
            # width grows with range (~1.73·r): the same nose that is
            # invisible 0.3 m out at 0.5 m off axis is comfortably inside
            # the cone at 0.9 m. Measured: 41 of 47 tracking losses were the
            # cone, not the mouth-plane blind spot.
            hold_r = max(plan.hold_r_m, 1.1) if blind else plan.hold_r_m
            return self._gate_hold(pose, hold_r, dt)
        return self._path_follow(pose, err, plan.v_des, dt)

    def _path_follow(
        self,
        pose: Pose,
        err: _AxisErrors,
        v_des: float,
        dt: float,
        *,
        min_forward_gf: float | None = None,
    ) -> ThrustCommand:
        """Boom placement: HEADING places the nose, THRUST closes the range.

        The docking probe is 0.3 m proud of the envelope in the 2D vehicle
        and 0.585 m in the MuJoCo rig, and the funnel judges where the NOSE
        is — so yaw is a lateral actuator, and a violently strong one:

            l_nose = l_body + arm·sin(heading − axis)

        v1 (and the first v2 cut) steered by pointing at the desired force
        vector, which for a 3 gf draft means 45-90° of heading — swinging the
        capture point half a metre and oscillating the lateral loop. Measured
        in MuJoCo: nose cross-error cycling ±1 m at the gate, the commit
        window never opening.

        So command the heading KINEMATICALLY instead — the angle that puts
        the nose on the corridor — and let thrust magnitude carry the closing
        speed:

            sin φ = (l_body + τ·v_body) / arm + draft̂/F      (φ = crab)

        The two terms agree at equilibrium, which is the useful part: holding
        a crosswind needs F·sin φ = draft, and the SAME φ puts the body
        exactly arm·sin φ downwind of the corridor with the boom reaching
        back onto it. The vehicle crabs into the draft and the nose rides the
        axis. It also degrades well: with no thrust at all the yaw loop still
        holds the nose on the corridor while |l_body| < arm.
        """
        m = self.phys_cfg.effective_mass_kg
        to_gf = m / 9.80665e-3
        g = self.nav.gains
        arm = max(0.05, self.phys_cfg.nose_arm_m)
        ax, ay = self._axis
        est = self.draft.estimate
        # body cross-track: strip the boom's yaw offset out of the nose fix
        l_body = err.lateral_m - arm * math.sin(pose.heading_rad - self._axis_angle)
        v_body = -pose.vx * ay + pose.vy * ax
        d_lat = est.lateral_gf(self._axis) * est.confidence
        crab_ff = min(0.9, max(-0.9, d_lat / max(3.0, abs(self._last_thrust_gf))))
        sin_phi = min(0.95, max(-0.95, (l_body + 2.0 * v_body) / arm + crab_ff))
        phi = math.asin(sin_phi)
        heading_des = wrap_angle(self._approach_heading + phi)
        hdg_err = wrap_angle(heading_des - pose.heading_rad)
        # ANCHOR: through a big turn the thrust points nowhere useful and a
        # bare pirouette lets the draft rebuild the offset being turned
        # toward. Station-keep (integrators included — that is the draft
        # trim) and yaw onto the target heading, then fly.
        if abs(hdg_err) > 1.05 and err.range_m > 0.45:
            if self._hold_pt is None:
                self._hold_pt = (pose.x, pose.y)
            hpx, hpy = self._hold_pt
            hfx, hfy, hfz = self.nav.goto_force(pose, hpx, hpy, self.dock_pose.z, dt,
                                                v_max=0.2)
            hfx += self.nav.ix
            hfy += self.nav.iy
            ch, sh = math.cos(pose.heading_rad), math.sin(pose.heading_rad)
            return self.nav.steer_command(
                pose, hfx * ch + hfy * sh, hfz - self._buoy_ff_gf, heading_des,
                min_forward_gf=min_forward_gf,
            )
        self._hold_pt = None
        # thrust magnitude: the closing demand, delivered through the crab,
        # floored by the lateral force the draft is taking off the top
        f_ax = g.kv * (v_des - err.v_axis_mps) * to_gf
        thrust = f_ax / max(0.35, math.cos(phi))
        thrust = max(thrust, abs(d_lat) / max(0.25, abs(sin_phi)))
        # Brake in the FAR field only: reverse thrust runs the boom backwards
        # through the same kinematics, and inside half a metre that puts the
        # capture point where it is not wanted. Speed is a far-field problem
        # and the planner will not commit until it is solved.
        floor = -4.0 if err.range_m > 0.45 else 0.0
        thrust = min(13.0, max(floor, thrust))
        self._last_thrust_gf = thrust
        # honest projection: a vehicle mid-yaw delivers only the component it
        # is actually pointing at
        forward_gf = thrust * math.cos(hdg_err)
        fz = (
            (-2.5 * err.vertical_m - 2.2 * pose.vz) * to_gf
            - self._buoy_ff_gf
            - est.z_gf * est.confidence
        )
        self.nav.integrate(0.0, 0.0, -err.vertical_m, dt)
        return self.nav.steer_command(
            pose, forward_gf, fz, heading_des, min_forward_gf=min_forward_gf
        )

    def _capture_pending(
        self, pose: Pose, err: _AxisErrors, capture: CaptureTelemetry, dt: float
    ) -> ThrustCommand:
        if capture.confirmed:
            self._enter(DockPhase.CAPTURED)
            return ThrustCommand()
        v = self.slide.update(err, capture, dt)
        if v.abort is not None:
            self._abort(v.abort)
            return ThrustCommand()
        if v.back_to_approach:
            # bounced clear of the mouth (or leaning on a rim we never
            # entered): a fresh line to plan, not a failed attempt. The
            # lockout matters — without it FINAL_APPROACH sees range < 12 cm
            # and hands straight back, and the pair ping-pong at 1 tick each
            # while 6 gf pushes the nose through the dock face.
            self._no_reenter = True
            self.replans += 1
            self._enter(DockPhase.FINAL_APPROACH)
            return self._path_follow(pose, err, 0.09, dt)
        to_gf = self.phys_cfg.effective_mass_kg / 9.80665e-3
        hold_gf = max(v.push_gf, self.dock_cfg.min_slide_thrust_gf + 2.0)
        if v.hold_thrust:
            # Nose is AT/INSIDE the mouth: freeze attitude (a yaw jump would
            # swing the nose arm off-axis right at the throat) and hold the
            # slide thrust — dropping below min_slide stalls + backs out
            # (research/06 §B.1). The cone wall centres us now, so the
            # vertical channel follows the FILTERED error: chasing σ-5 cm
            # dead reckoning inside the cone is noise, not control.
            fz = (-2.0 * v.vertical_m - 2.0 * pose.vz) * to_gf - self._buoy_ff_gf
            return self.nav.force_to_command(
                pose, 0.0, 0.0, fz,
                heading_des=pose.heading_rad, min_forward_gf=hold_gf, dt=dt,
            )
        # Last free-flight centimetres: NO hold floor yet — thrust-flooring
        # before contact slams the nose past v_max_capture and bounces.
        # Keep homing gently down to contact speed.
        return self._path_follow(pose, err, 0.07, dt)

    def _release(self, pose: Pose, err: _AxisErrors,
                 capture: CaptureTelemetry) -> ThrustCommand:
        if capture.capture_switch:
            return ThrustCommand()  # remanence still holding — wait it out
        if err.range_m > 0.6:
            self._enter(DockPhase.DEPARTED)
            self._enter(DockPhase.FLYING)
            return ThrustCommand()
        cmd = self.nav.force_to_command(
            pose, 0.0, 0.0, 0.0, heading_des=self._approach_heading
        )
        cmd.forward_gf = -8.0  # back straight out of the mouth
        return cmd

    def _errors(self, pose: Pose, relpose: RelativePose) -> _AxisErrors:
        from meemoo.flight.docking import _AxisErrors as AE

        fresh = relpose.tracking_valid and relpose.tracking_age_ms < _TRACKING_STALE_MS
        ax, ay = self._axis
        # NOSE lateral velocity: the camera tracks the nose, so the rate must
        # include the yaw-arm coupling (d/dt of arm·sin(heading−axis))
        vl = (
            -pose.vx * ay
            + pose.vy * ax
            + self.phys_cfg.nose_arm_m
            * math.cos(pose.heading_rad - self._axis_angle)
            * pose.yaw_rate
        )
        v_axis = -(pose.vx * ax + pose.vy * ay)
        if fresh:
            return AE(
                range_m=relpose.range_to_throat_mm / 1000.0,
                lateral_m=relpose.lateral_error_mm / 1000.0,
                vertical_m=relpose.vertical_error_mm / 1000.0,
                v_axis_mps=v_axis, v_lat_mps=vl, fresh=True,
            )
        # fallback: nose geometry from the coarse room pose (σ 5 cm)
        arm = self.phys_cfg.nose_arm_m
        nx = pose.x + arm * math.cos(pose.heading_rad)
        ny = pose.y + arm * math.sin(pose.heading_rad)
        nz = pose.z + arm * math.sin(pose.swing_rad)
        dx, dy = nx - self.dock_pose.x, ny - self.dock_pose.y
        return AE(
            range_m=dx * ax + dy * ay,
            lateral_m=-dx * ay + dy * ax,
            vertical_m=nz - self.dock_pose.z,
            v_axis_mps=v_axis, v_lat_mps=vl, fresh=False,
        )
