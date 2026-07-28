"""MjWorld — the MuJoCo runtime for the Meemoo 3D rig.

Owns what the engine cannot express declaratively: net buoyancy (upward
force M*g + b(t), b drifting +-5 gf, applied at the sphere CENTER so the
buoyancy-vs-COM couple creates the pendulum from first principles); HVAC
drafts as an OU-wandering WIND vector through the engine's fluid drag; the
electromagnet (weld equality, engages under 15 mm with retention commanded,
0.5 s remanence on release); the A5 speed governor; passive fin damping
(the one hand rotational constant — documented); and the linear ADDED-MASS
reaction. That last one is a verified engine gap (2026-07-28, MuJoCo 3.10,
all integrators): the engine computes the ellipsoid virtual-mass
coefficient (geom_fluid[6:9]*density = 0.5*rho*V for a sphere) but never
applies -m_A*dv/dt — a sphere in density-1000 fluid accelerates at F/m.
"The blimp coasts" is an Art. II SectionG must-have, so we apply the force
here using the ENGINE'S OWN coefficient, lagged one substep.
"""

from __future__ import annotations

import math
import random
from typing import Any

import mujoco
import numpy as np

from sim3d.model import build_xml
from sim3d.spec import GF_TO_N, G, Rig3DConfig, mix_thrust

# Engine buffers. numpy is absent from the default (CI) env, so a real
# ndarray type cannot appear in annotations; explicit Any keeps mypy strict
# green with and without the physics3d group installed.
FloatArray = Any


class MjWorld:
    """One vehicle + one dock in one MuJoCo scene."""

    def __init__(
        self,
        cfg: Rig3DConfig | None = None,
        *,
        seed: int = 0,
        buoyancy_gf: float | None = None,
        drafts_enabled: bool = True,
    ) -> None:
        self.cfg = cfg or Rig3DConfig()
        self.model = mujoco.MjModel.from_xml_string(build_xml(self.cfg))
        self.data = mujoco.MjData(self.model)
        self.rng = random.Random(seed)
        self.body_id = int(
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "blimp")
        )
        self._sid_center = self._site("center")
        self._sid_tip = self._site("tip_site")
        self._sid_throat = self._site("throat")
        self._gid_tip = int(
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "tip")
        )
        self._gid_plate = int(
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "throat_plate")
        )
        self._eq_capture = int(
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_EQUALITY, "capture")
        )
        self.buoyancy_gf = (
            buoyancy_gf if buoyancy_gf is not None else -3.0  # 2D default trim
        )
        self._drafts = drafts_enabled
        self._wind = [0.0, 0.0, 0.0]
        b = self.cfg.wind_bias_max
        ang = self.rng.uniform(0.0, 2.0 * math.pi)
        mag = self.rng.uniform(0.0, b)
        self._wind_bias = (
            (mag * math.cos(ang), mag * math.sin(ang)) if drafts_enabled else (0.0, 0.0)
        )
        self.retention_commanded = False
        self.charge_enabled = False
        self._remanence_until = -1.0
        # per-motor gf currently applied (post-mixer, pre-governor)
        self._motors_gf = (0.0, 0.0, 0.0, 0.0)
        # bookkeeping for the experiment
        self.mouth_entries = 0
        self.last_entry_speed: float | None = None
        self.min_tip_throat = float("inf")
        self._prev_tip_x: float | None = None
        self._hover_duty_lp = 0.0
        # engine-owned added mass (see module docstring): 0.5*rho*V for the
        # sphere, read back from the compiled model, applied as -m_A*a_prev
        gid = int(mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "envelope"))
        self.added_mass_kg = float(self.model.geom_fluid[gid][6]) * float(
            self.model.opt.density
        )
        self._accel_est = np.zeros(3)
        mujoco.mj_forward(self.model, self.data)

    def _site(self, name: str) -> int:
        return int(mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, name))

    # ------------------------------------------------------------------ state
    def reset_pose(
        self, x: float, y: float, z: float, heading: float
    ) -> None:
        """Teleport the vehicle (episode start); zeroes velocity + weld."""
        d = self.data
        d.qpos[:] = 0.0
        d.qpos[0:3] = (x, y, z)
        d.qpos[3] = math.cos(heading / 2.0)
        d.qpos[6] = math.sin(heading / 2.0)
        d.qvel[:] = 0.0
        d.eq_active[self._eq_capture] = 0
        d.ctrl[:] = 0.0
        self.retention_commanded = False
        self._remanence_until = -1.0
        self._prev_tip_x = None
        self.mouth_entries = 0
        self.last_entry_speed = None
        self.min_tip_throat = float("inf")
        self._accel_est = np.zeros(3)
        mujoco.mj_forward(self.model, self.data)

    @property
    def t(self) -> float:
        return float(self.data.time)

    def site_pos(self, sid: int) -> tuple[float, float, float]:
        p = self.data.site_xpos[sid]
        return (float(p[0]), float(p[1]), float(p[2]))

    @property
    def tip_pos(self) -> tuple[float, float, float]:
        return self.site_pos(self._sid_tip)

    @property
    def center_pos(self) -> tuple[float, float, float]:
        return self.site_pos(self._sid_center)

    @property
    def tip_throat_dist(self) -> float:
        tp = self.data.site_xpos[self._sid_tip]
        th = self.data.site_xpos[self._sid_throat]
        return float(np.linalg.norm(tp - th))

    @property
    def welded(self) -> bool:
        return bool(self.data.eq_active[self._eq_capture])

    @property
    def tip_plate_contact(self) -> bool:
        d = self.data
        pair = {self._gid_tip, self._gid_plate}
        return any(
            {int(d.contact.geom1[i]), int(d.contact.geom2[i])} == pair
            for i in range(d.ncon)
        )

    def velocity(self) -> tuple[FloatArray, FloatArray]:
        """(angular, linear) world-frame velocity of the body frame origin."""
        res = np.zeros(6)
        mujoco.mj_objectVelocity(
            self.model, self.data, mujoco.mjtObj.mjOBJ_BODY, self.body_id, res, 0
        )
        return res[0:3].copy(), res[3:6].copy()

    def rotation(self) -> FloatArray:
        return np.asarray(self.data.xmat[self.body_id], dtype=float).reshape(3, 3)

    # -------------------------------------------------------------- actuation
    def set_motors(self, forward_gf: float, vertical_gf: float, yaw_gf: float) -> None:
        self._motors_gf = mix_thrust(forward_gf, vertical_gf, yaw_gf, self.cfg)

    def set_retention(self, on: bool) -> None:
        if self.retention_commanded and not on:
            self._remanence_until = self.t + self.cfg.remanence_s
        self.retention_commanded = on

    # ------------------------------------------------------------------ step
    def step(self, dt: float, *, external_force_n: tuple[float, float, float] | None = None
             ) -> None:
        """Advance by dt (integer number of physics substeps)."""
        n = max(1, round(dt / self.cfg.timestep))
        for _ in range(n):
            self._substep(external_force_n)

    def _substep(self, ext: tuple[float, float, float] | None) -> None:
        cfg, m, d = self.cfg, self.model, self.data
        h = m.opt.timestep
        self._update_buoyancy(h)
        self._update_wind(h)
        d.qfrc_applied[:] = 0.0
        self._apply_ctrl()
        # net buoyancy at the CENTER of the sphere (center of buoyancy)
        lift = cfg.total_mass * G + self.buoyancy_gf * GF_TO_N
        center = d.site_xpos[self._sid_center]
        mujoco.mj_applyFT(
            m, d, np.array([0.0, 0.0, lift]), np.zeros(3), center,
            self.body_id, d.qfrc_applied,
        )
        if ext is not None:
            mujoco.mj_applyFT(
                m, d, np.array(ext, dtype=float), np.zeros(3), center,
                self.body_id, d.qfrc_applied,
            )
        # added-mass reaction at the envelope center, engine coefficient,
        # previous-substep acceleration (skipped while welded: dock holds it)
        if not self.welded:
            mujoco.mj_applyFT(
                m, d, -self.added_mass_kg * self._accel_est, np.zeros(3), center,
                self.body_id, d.qfrc_applied,
            )
        self._apply_fin_damping()
        _, v_before = self.velocity()
        mujoco.mj_step(m, d)
        _, v_after = self.velocity()
        # mild relaxation damps the one-step-lag ringing of the scheme
        self._accel_est = 0.3 * self._accel_est + 0.7 * (v_after - v_before) / h
        self._magnet_logic()
        self._bookkeep(h)

    def _apply_ctrl(self) -> None:
        """Per-motor gf -> ctrl (N), with the A5 governor applied honestly."""
        left, right, vfront, vback = self._motors_gf
        _, v = self.velocity()
        speed = float(np.linalg.norm(v))
        if speed >= self.cfg.max_speed_mps:
            rot = self.rotation()
            thrust = rot[:, 0] * (left + right) * GF_TO_N + rot[:, 2] * (
                (vfront + vback) * GF_TO_N
            )
            if float(np.dot(thrust, v)) > 0.0:  # thrusting along velocity: cut
                left = right = vfront = vback = 0.0
        self.data.ctrl[0] = left * GF_TO_N
        self.data.ctrl[1] = right * GF_TO_N
        self.data.ctrl[2] = vfront * GF_TO_N
        self.data.ctrl[3] = vback * GF_TO_N

    def _apply_fin_damping(self) -> None:
        cfg = self.cfg
        w_world, _ = self.velocity()
        rot = self.rotation()
        w_body = rot.T @ w_world
        tau_body = np.array([
            -cfg.fin_rot_damping_nms * w_body[0],
            -cfg.fin_rot_damping_nms * w_body[1],
            -cfg.yaw_drag_nms * w_body[2],
        ])
        com = self.data.xipos[self.body_id]
        mujoco.mj_applyFT(
            self.model, self.data, np.zeros(3), rot @ tau_body, com,
            self.body_id, self.data.qfrc_applied,
        )

    def _update_buoyancy(self, h: float) -> None:
        cfg = self.cfg
        self.buoyancy_gf += self.rng.gauss(0.0, cfg.buoyancy_walk_sigma_gf) * math.sqrt(h)
        c = cfg.buoyancy_clamp_gf
        self.buoyancy_gf = min(c, max(-c, self.buoyancy_gf))

    def _update_wind(self, h: float) -> None:
        if not self._drafts:
            return
        cfg = self.cfg
        for i in range(3):
            frac = cfg.wind_vertical_frac if i == 2 else 1.0
            w = self._wind[i]
            w += (-w / cfg.wind_tau_s) * h + self.rng.gauss(0.0, cfg.wind_sigma * frac)
            clamp = cfg.wind_axis_clamp * frac
            self._wind[i] = min(clamp, max(-clamp, w))
        wx = self._wind[0] + self._wind_bias[0]
        wy = self._wind[1] + self._wind_bias[1]
        wz = self._wind[2]
        speed = math.sqrt(wx * wx + wy * wy + wz * wz)
        if speed > cfg.wind_speed_cap:
            k = cfg.wind_speed_cap / speed
            wx, wy, wz = wx * k, wy * k, wz * k
        self.model.opt.wind[:] = (wx, wy, wz)

    def _magnet_logic(self) -> None:
        d = self.data
        if self.retention_commanded or self.t < self._remanence_until:
            if not self.welded and self.tip_throat_dist < self.cfg.magnet_engage_m:
                d.eq_active[self._eq_capture] = 1
        elif self.welded:
            d.eq_active[self._eq_capture] = 0

    def _bookkeep(self, h: float) -> None:
        tip = self.data.site_xpos[self._sid_tip]
        self.min_tip_throat = min(self.min_tip_throat, self.tip_throat_dist)
        prev = self._prev_tip_x
        self._prev_tip_x = float(tip[0])
        if prev is not None and prev > 0.0 >= tip[0]:
            radial = math.hypot(float(tip[1]), float(tip[2]) - self.cfg.dock_z)
            if radial < self.cfg.mouth_radius + 0.05:
                self.mouth_entries += 1
                _, v = self.velocity()
                self.last_entry_speed = float(np.linalg.norm(v))
        vert_gf = (float(self.data.ctrl[2]) + float(self.data.ctrl[3])) / GF_TO_N
        duty = vert_gf / (2.0 * self.cfg.thrust_fwd_max_gf)
        self._hover_duty_lp += (duty - self._hover_duty_lp) * min(1.0, h / 3.0)

    @property
    def net_buoyancy_est_gf(self) -> float:
        """Hover-duty inversion, exactly as the 2D sim and the real dock."""
        return -self._hover_duty_lp * 2.0 * self.cfg.thrust_fwd_max_gf
