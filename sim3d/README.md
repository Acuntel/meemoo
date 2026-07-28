# sim3d — MuJoCo cross-validation rig (Phase 10)

The 2D sim in `meemoo/flight` is the product truth the docking controller
was built against. This package rebuilds the same vehicle and dock in
MuJoCo so that the load-bearing physics comes from an independent engine,
then flies the **unmodified** `DockingController` against it. The honest
numbers live in `docs/PHYSICS_VALIDATION.md`.

## What is modeled

- **Vehicle**: 0.61 m sphere, 125 g all-up (58 g thin-shell envelope, 2 g
  nose probe, 65 g gondola hung rigidly 0.15 m below center). The pendulum
  mode is emergent: net buoyancy is applied at the sphere center while
  gravity acts at the COM 78 mm lower — nothing is scripted.
- **Fluid**: MuJoCo's ellipsoid fluid model (`fluidshape="ellipsoid"`,
  air density 1.204), blunt-drag coefficient tuned to the measured sphere
  Cd 0.47. Drag, angular damping, and the virtual-mass coefficient come
  from the engine. One caveat we verified empirically: MuJoCo computes the
  virtual-mass coefficient but never applies the linear acceleration-
  reaction force, so `world.py` applies `-m_A * a` using the **engine's own
  coefficient** (0.5 * rho * V = 71.5 g), lagged one substep.
- **Thrust**: 4 site-transmission actuators (2 forward differential, 2
  vertical) with `-5..+10 gf` per-motor `ctrlrange` enforced by the engine;
  the same mixer math as the 2D sim; thrust tilts with the body.
- **Dock**: the assigned cone — 40 cm mouth to 12 cm throat over 35 cm,
  horizontal axis at 1.2 m — built from 32 static panels, plus a centering
  cup (12 cm -> 1.2 cm over the last 6 cm) that the geometry forces (see
  finding 1 in the validation doc). Magnet = a weld equality that engages
  when the probe tip is within 15 mm of the throat while retention is
  commanded; release keeps a 0.5 s remanence window.
- **Environment**: net buoyancy drifting in +-5 gf (both signs, per
  episode, random walk), HVAC drafts as OU-wandering **wind** through the
  engine's fluid drag (a few gf at the vehicle), 2.4 m ceiling, walls.
- **Telemetry/commands**: `sim3d/adapter.py` reproduces the 2D contract —
  sigma-5 cm room pose, 20 Hz dock camera with FOV and noise, two-signal
  capture, ~100 ms command latency — so the controller runs unmodified.

## Running it

```bash
# one-time (also happens automatically via uv run --group):
uv add --group physics3d mujoco     # already in pyproject

# the full experiment (200 docking episodes x {50 Hz, 10 Hz} + 100 bump
# pairs + trajectory plots into docs/assets/):
make physics3d

# pieces:
uv run --group physics3d python -m sim3d.experiment --episodes 20 --bumps 5
uv run --group physics3d python -m sim3d.model > /tmp/meemoo3d.xml  # inspect MJCF
uv run --group physics3d pytest tests/sim3d
```

`make check` never needs mujoco: the sim3d tests skip cleanly when the
group is not installed, and mujoco is not a dependency of the app.

## Rules

Do **not** tune the controller to pass here. If it fails in MuJoCo, the
failure modes and numbers are the deliverable. Physics constants follow
the same law as the 2D sim (Constitution Art. II Section 4): never loosen
them to make a controller look good.
