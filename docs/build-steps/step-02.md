# Step 02 — Perception: the eyes (base-station camera)

**Goal:** person detection, pose, and the fall state machine — persistence-primary.
**Read first:** docs/research/05-fall-detection.md §A (algorithm, signals,
thresholds, state machine, suppression logic — implement EXACTLY this, it
supersedes the MASTER_PROMPT's simpler heuristic), §B (test fixtures), §F (CPU
duty cycle); CONSTITUTION Art. IV.8.

## Build

1. `VideoSource` interface: `webcam` (default) | `mjpeg_url` | `file`. This is
   the future-hardware swap point — keep it pure.
2. Duty-cycle pipeline per research §F.3: IDLE motion gate (3 fps frame-diff) →
   ACTIVE MediaPipe Pose Full @ 15 fps → TRACKING during candidates. The motion
   gate must NOT be the only path in — once a person is seen, pose keeps running
   until confirmed-gone (research §F.3 subtlety).
3. Signals module: torso_angle, support_y, elevation, v_descent, motion_energy,
   vis_frac, aspect — all torso-length-normalized (formulas in research §A.1).
4. Floor-line + furniture-zone calibration with learning phase (research §A.2):
   floor fit from upright frames, zone grid from stable sits/lies, YOLOv8n COCO
   bootstrap, guided placement check, reduced-sensitivity first 7–14 days.
5. Fall state machine (research §A.4 diagram + §A.3 thresholds as a committed
   `golden_thresholds.json`): UPRIGHT→DESCENDING→GROUNDED_CANDIDATE→
   CONFIRMED_DOWN→VERIFYING(→ESCALATE) + RECOVERED, PLUS parallel LONG_LIE and
   VANISHED_DOWN paths, CANDIDATE_SOFT, ballistic-override of furniture
   suppression (§A.5 code). Emits `candidate.fall` (~5 s), `person.down` (15 s),
   `person.recovered` on the bus.
6. Presence tracking + thumbnails + rolling 60 s skeleton ring buffer (JSONL)
   per candidate event. Annotated feed (boxes, skeleton, state label) published
   for the /ws/video endpoint (endpoint itself lands in step 07).
7. Test fixtures per research §B: fetch scripts for GMDCSA-24 + CaucaFall,
   extract landmark JSONL → `tests/fixtures/landmarks/` (committed; raw clips
   gitignored). pytest: the three spec scenarios, asserting per-event recall
   100% at candidate stage on bundled fall clips, false-candidate rate per
   ADL-minute, time-to-candidate distribution.

## Gate
- All perception tests green against the landmark fixtures.
- Live demo: webcam window shows annotated pose; lying on the floor (or playing
  a fall clip via `file` source) fires `candidate.fall` then `person.down`;
  standing up fires `person.recovered`.
