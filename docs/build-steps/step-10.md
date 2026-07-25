# Step 10 — 3D simulation investigation (NVIDIA Isaac)

**Goal:** decide whether Isaac Sim earns a place in the pipeline, per Brady's
request to "build it out in software and test it in 3D on the computer."
**Read first:** BUILD_PLAN §4; research/06 §G (what any sim must model);
CONSTITUTION Art. II.5.

## Investigate

1. Requirements check: Isaac Sim needs an NVIDIA RTX GPU — Brady is on Mac.
   Cloud paths to evaluate (cost/hr, setup friction): AWS g6/g6e or g5 EC2
   (Brady has AWS accts; use brady-inkept 718897321985, us-east-2), NVIDIA
   Brev, or Omniverse on a rented workstation. Estimate $/month for a
   realistic tuning workload.
2. Physics fit: can Isaac model a buoyant body with added-mass, gram-force
   thrusters, and drifting buoyancy cleanly? (Buoyancy is not a native
   primitive — likely a custom force applier. Prototype it: a 0.61 m sphere,
   65 g payload, 4 thrust points, drafts as force fields.)
3. Port the docking task: recreate the step-06 docking scenario in 3D; compare
   controller behavior 2D-sim vs 3D-sim; measure whether 3D catches failure
   modes 2D misses (vertical approach errors, pendulum-yaw coupling).
4. Isaac Lab RL option: is training a docking policy worth it vs the tuned
   PID/state-machine controller? (Only pursue if the classical controller
   struggles in 3D.)

## Deliverable
`docs/ISAAC_DECISION.md`: verdict (adopt / defer / reject) with measured
evidence, monthly cost, and — if adopt — the workflow (2D sim stays the product
UI; Isaac becomes the control-tuning rig). Check off TODO Phase 10 either way.
