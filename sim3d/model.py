"""Programmatic MJCF for the Meemoo 3D rig (sphere + probe + dock cone).

Design decisions (all cross-checked against the 2D contract):
- The envelope is a thin-shell sphere with ``fluidshape="ellipsoid"`` so the
  ENGINE computes added mass, quadratic drag, and angular fluid drag from
  first principles (option density = 1.204). No hand added-mass constant.
- The gondola is a rigid 65 g point mass 0.15 m below center. Rigid, not a
  joint: on the real vehicle the gondola is bonded to the envelope, and the
  pendulum mode emerges from buoyancy (applied at sphere center by the
  world) vs gravity (at the COM, 78 mm lower) — nothing is scripted.
- Thrusters are site-transmission actuators, so thrust tilts with the body
  (the thrust-coupled pendulum from research/04 SectionF), and ctrlrange
  enforces the -5..+10 gf per-motor saturation inside the engine.
- The dock cone is 16 static panels; capture is a weld equality to the
  world, defined at the model's initial (seated) pose: relpose zeros makes
  the weld target qpos0, so the XML's initial pose IS the seated pose and
  episode resets teleport the vehicle to its random start afterwards.

Dump the XML for inspection: ``uv run --group physics3d python -m sim3d.model``.
"""

from __future__ import annotations

import math

from sim3d.spec import GF_TO_N, Rig3DConfig


def _frustum_panels(
    cfg: Rig3DConfig, prefix: str, x0: float, r0: float, x1: float, r1: float
) -> list[str]:
    """A conical frustum section: n thin boxes tiling the surface.

    x0/r0 is the wide (mouth-side) ring, x1/r1 the narrow ring; x1 < x0.
    """
    slant = math.hypot(x0 - x1, r0 - r1)
    sx = (x1 - x0) / slant  # slant direction, (x, radial) plane
    sr = (r1 - r0) / slant
    nx, nr = sr, -sx  # outward normal of the narrowing cone
    r_mid = (r0 + r1) / 2.0
    x_mid = (x0 + x1) / 2.0
    # width sized to the WIDE circumference so flat panels leave no gaps at
    # the wide end (they overlap near the narrow end, which is harmless)
    half_w = math.pi * r0 / cfg.n_panels * 1.05
    half_t = 0.004
    out: list[str] = []
    for i in range(cfg.n_panels):
        th = 2.0 * math.pi * i / cfg.n_panels
        c, s = math.cos(th), math.sin(th)
        # surface midpoint pushed out along the normal by half thickness
        px = x_mid + nx * half_t
        py = r_mid * c + nr * c * half_t
        pz = cfg.dock_z + r_mid * s + nr * s * half_t
        xaxis = (sx, sr * c, sr * s)
        yaxis = (0.0, -s, c)
        out.append(
            f'<geom name="{prefix}{i}" type="box" size="{slant / 2.0:.4f} '
            f'{half_w:.4f} {half_t}" pos="{px:.4f} {py:.4f} {pz:.4f}" '
            f'xyaxes="{xaxis[0]:.5f} {xaxis[1]:.5f} {xaxis[2]:.5f} '
            f'{yaxis[0]:.5f} {yaxis[1]:.5f} {yaxis[2]:.5f}"/>'
        )
    return out


def _cone_panels(cfg: Rig3DConfig) -> list[str]:
    """The full funnel: spec cone (40->12 cm) + the centering cup (12->1.2 cm)."""
    cup_start_x = -(cfg.cone_depth - cfg.cup_depth)
    return _frustum_panels(
        cfg, "cone", 0.0, cfg.mouth_radius, cup_start_x, cfg.throat_radius
    ) + _frustum_panels(
        cfg, "cup", cup_start_x, cfg.throat_radius, -cfg.cone_depth,
        cfg.cup_exit_radius,
    )


def _dock_face(cfg: Rig3DConfig) -> list[str]:
    """A square-annulus face plate around the mouth (the dock housing)."""
    a = cfg.mouth_radius + 0.01  # aperture half-width
    b = 0.70  # face half-extent
    t = 0.01
    x = -0.012
    z = cfg.dock_z
    w = (b - a) / 2.0
    return [
        f'<geom name="face_t" type="box" size="{t} {b} {w}" pos="{x} 0 {z + a + w}"/>',
        f'<geom name="face_b" type="box" size="{t} {b} {w}" pos="{x} 0 {z - a - w}"/>',
        f'<geom name="face_l" type="box" size="{t} {w} {a}" pos="{x} {a + w} {z}"/>',
        f'<geom name="face_r" type="box" size="{t} {w} {a}" pos="{x} {-a - w} {z}"/>',
    ]


def _room(cfg: Rig3DConfig) -> list[str]:
    x0, x1 = cfg.room_x
    y0, y1 = cfg.room_y
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    hx, hy = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    zc = cfg.ceiling / 2.0
    return [
        '<geom name="floor" type="plane" size="6 6 0.1" pos="2 0 0"/>',
        f'<geom name="ceiling" type="box" size="{hx} {hy} 0.05" '
        f'pos="{cx} {cy} {cfg.ceiling + 0.05}"/>',
        f'<geom name="wall_back" type="box" size="0.05 {hy} {zc}" '
        f'pos="{x0 - 0.05} {cy} {zc}"/>',
        f'<geom name="wall_front" type="box" size="0.05 {hy} {zc}" '
        f'pos="{x1 + 0.05} {cy} {zc}"/>',
        f'<geom name="wall_left" type="box" size="{hx} 0.05 {zc}" '
        f'pos="{cx} {y1 + 0.05} {zc}"/>',
        f'<geom name="wall_right" type="box" size="{hx} 0.05 {zc}" '
        f'pos="{cx} {y0 - 0.05} {zc}"/>',
    ]


def _blimp(cfg: Rig3DConfig) -> str:
    r = cfg.envelope_radius
    probe_start = r - 0.01
    tip_center = cfg.tip_reach - cfg.tip_radius
    my, vx = cfg.motor_y, cfg.vmotor_x
    gz = -cfg.gondola_drop
    # static trim ballast: shift the gondola aft so the probe's nose moment
    # cancels and the vehicle hangs level (any real build would balance this)
    probe_com_x = (probe_start + tip_center) / 2.0
    gx = -cfg.probe_mass * probe_com_x / cfg.gondola_mass
    return f"""
    <body name="blimp" pos="{cfg.seated_center_x:.4f} 0 {cfg.dock_z}" quat="0 0 0 1">
      <freejoint name="free"/>
      <geom name="envelope" type="sphere" size="{r}" mass="{cfg.shell_mass}"
            shellinertia="true" fluidshape="ellipsoid"
            fluidcoef="{cfg.fluidcoef}"/>
      <geom name="probe" type="capsule" fromto="{probe_start} 0 0 {tip_center:.4f} 0 0"
            size="0.008" mass="{cfg.probe_mass}"/>
      <geom name="tip" type="sphere" size="{cfg.tip_radius}"
            pos="{tip_center:.4f} 0 0" mass="0.0"/>
      <geom name="gondola" type="box" size="0.05 0.03 0.03" pos="{gx:.4f} 0 {gz}"
            mass="{cfg.gondola_mass}"/>
      <site name="center" pos="0 0 0" size="0.005"/>
      <site name="tip_site" pos="{cfg.tip_reach} 0 0" size="0.003"/>
      <site name="m_left" pos="0 {my} {gz}" size="0.004"/>
      <site name="m_right" pos="0 {-my} {gz}" size="0.004"/>
      <site name="m_vfront" pos="{vx} 0 {gz}" size="0.004"/>
      <site name="m_vback" pos="{-vx} 0 {gz}" size="0.004"/>
    </body>"""


def build_xml(cfg: Rig3DConfig | None = None) -> str:
    """The full MJCF document as a string."""
    cfg = cfg or Rig3DConfig()
    fwd_n = cfg.thrust_fwd_max_gf * GF_TO_N
    rev_n = cfg.thrust_rev_max_gf * GF_TO_N
    plate_x = -(cfg.cone_depth + 0.0045)  # 0.5 mm seated tip penetration
    fixed = "\n    ".join(
        _room(cfg)
        + _cone_panels(cfg)
        + _dock_face(cfg)
        + [
            f'<geom name="throat_plate" type="cylinder" size="0.03 0.005" '
            f'pos="{plate_x:.4f} 0 {cfg.dock_z}" euler="0 90 0"/>',
            f'<site name="mouth" pos="0 0 {cfg.dock_z}" size="0.005"/>',
            f'<site name="throat" pos="{-cfg.cone_depth} 0 {cfg.dock_z}" size="0.005"/>',
        ]
    )
    motors = "\n    ".join(
        f'<general name="{name}" site="{site}" gear="{gear}" '
        f'ctrllimited="true" ctrlrange="{-rev_n:.5f} {fwd_n:.5f}"/>'
        for name, site, gear in (
            ("thrust_left", "m_left", "1 0 0 0 0 0"),
            ("thrust_right", "m_right", "1 0 0 0 0 0"),
            ("thrust_vfront", "m_vfront", "0 0 1 0 0 0"),
            ("thrust_vback", "m_vback", "0 0 1 0 0 0"),
        )
    )
    return f"""<mujoco model="meemoo3d">
  <option timestep="{cfg.timestep}" gravity="0 0 -9.80665" density="{cfg.air_density}"
          viscosity="{cfg.air_viscosity}" wind="0 0 0" integrator="implicitfast"/>
  <default>
    <geom friction="0.3 0.005 0.0001" solref="0.015 0.7"/>
  </default>
  <worldbody>
    {fixed}
    {_blimp(cfg)}
  </worldbody>
  <actuator>
    {motors}
  </actuator>
  <equality>
    <!-- The electromagnet: 2.5 kg-class holding force vs a 125 g vehicle is
         effectively rigid, so the weld is made stiff enough to actually
         seat the tip on the plate against cup-wall contact/friction. -->
    <weld name="capture" body1="blimp" active="false" solref="0.004 1"
          solimp="0.95 0.99 0.0001 0.5 2"/>
  </equality>
</mujoco>
"""


if __name__ == "__main__":  # pragma: no cover - inspection helper
    print(build_xml())  # noqa: T201
