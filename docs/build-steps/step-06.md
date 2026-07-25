# Step 06 — Flight + dock: the honest-physics simulator

**Goal:** `FlightController` + `DockController`, a 2D sim whose physics tell the
truth, and a docking controller that hits >95% in sim.
**Read first:** research/06 §G (interfaces, states, telemetry, the five sim
must-models — implement ALL five), research/04 §A (constants: 120 L sphere,
0.61 m, 65 g payload, ~10 gf/motor), §F (pendulum/swing); CONSTITUTION Art. I.2,
II.3–5, IV.6; BUILD_PLAN §2 (actuator model: props fly it, fins damp it).

## Build

1. `FlightController` interface per spec: takeoff/land/goto/patrol/hold/
   return_to_dock/battery_status/position — plus attitude + netBuoyancy_gf
   telemetry. Sibling `DockController`: setRetention, setChargeEnabled, capture
   telemetry (retentionEngaged, contactContinuity, captureSwitch — two-signal
   confirmation rule).
2. `SimulatedBlimp` (2D top-down, JSON floor plans; ship default apartment +
   facility wing) with the five honest-physics requirements from research/06 §G:
   added-mass ≈ 2× inertia; buoyancy as a slowly-drifting ±5 gf parameter
   randomized per episode; thrust saturation ~10 gf/thruster; funnel capture
   model (R_capture, v_max → bounce/abort); low-frequency HVAC draft force
   fields of a few gf. Battery drain (20 min full→empty), recharge on dock,
   auto-return <25%. Negative trim (2–4 g heavy) is the default state.
3. Docking state machine per research/06 §G: FLYING → DOCK_REQUESTED → TRANSIT →
   ALIGN → FINAL_APPROACH → CAPTURE_PENDING → CAPTURED → CHARGING →
   CHARGE_COMPLETE → RELEASE → DEPARTED, ABORT+retry, DOCK_FAILED after N.
   Controller runs base-station-side against sim telemetry with ~100 ms
   simulated command latency.
4. Swing damping: pendulum oscillation modeled; IMU-rate-feedback damper
   (the published "swing-reducer" pattern) as part of the controller.
5. Rounds: waypoint routes; at a person waypoint guardian runs the REAL voice
   check-in (sim is fake; the check-in is real). Helium level decay + top-off
   button + dock load-cell trim reading in the data model and sim.
6. `MqttBlimp` stub: full MQTT protocol spec in docstrings (topics for
   telemetry/commands/video handoff; constants: ESP32-S3 XIAO Sense, 65 g,
   120 L sphere, negative trim, prop+fin actuator map) — methods raise
   NotImplementedError carrying the spec.
7. Sprite/rendering data for the web sim (position/heading/state stream) —
   the actual UI lands in step 07; here, expose /ws/sim-ready state.

## Gate
- pytest: docking success >95% first-attempt across 200 randomized episodes
  (buoyancy ±5 gf both signs, drafts on), >99% with one retry; capture NEVER
  confirms on a single signal; battery auto-return works; a controller tuned
  with honest physics STAYS tuned when constants perturb ±20%.
- Manual: watch the whale drift a full round in a debug view, dock, charge,
  depart.
