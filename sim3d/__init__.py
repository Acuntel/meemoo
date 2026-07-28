"""MuJoCo 3D cross-validation rig for the docking controller (Phase 10).

The 2D sim (meemoo/flight) is the product truth the controller was built
against; this package rebuilds the same vehicle + dock in MuJoCo so that
ADDED MASS and DRAG come from the engine's ellipsoid fluid model instead of
our hand-derived constants, and re-runs the UNMODIFIED
:class:`meemoo.flight.docking.DockingController` against it.

Nothing here is a product dependency: mujoco lives in the optional
``physics3d`` dependency group, and every test that needs it skips cleanly
when it is absent. Run ``make physics3d`` for the full experiment; see
sim3d/README.md and docs/PHYSICS_VALIDATION.md for the honest numbers.
"""
