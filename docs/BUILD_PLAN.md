# Meemoo — Master Build Plan (feasibility-checked)

> Created 2026-07-25. Read this before executing any build step. The step-by-step
> execution prompts live in `docs/build-steps/`; run them with `/build-step <n>`
> after `/clear` — each step is self-contained because context lives in the repo.

## 1. Feasibility verdict

Every load-bearing claim was researched before this plan (docs/research/01–07):

| Claim | Verdict | Evidence |
|---|---|---|
| A ~0.6 m helium sphere can carry the electronics | ✅ ~120 L lifts ~75 g vs ~50 g BOM | research/04 §A (validated within 2% against published platforms) |
| Near-silent flight | ✅ physics gift; est. 35–45 dB @ 1 m | research/04 §D (bench-verify, Phase 9) |
| A dumb aircraft + smart base station can fly it | ✅ done by Georgia Tech, Edinburgh, Auckland | research/06 prior art |
| It can dock + recharge itself | ⚠️ never demonstrated for micro-blimps — our hardest problem, solvable design exists (cone + held thrust + dock electromagnet + ring contacts) | research/06 |
| Fall detection on CPU webcam works | ✅ deployed products prove it; persistence-primary algorithm specified | research/05 |
| Voice loop fully self-hosted at <1 s | ✅ on Mac-mini-class hardware | research/02 |
| Legal to build & pilot (IL/CA) | ✅ prototype yes; go-live gates defined | research/03, CONSTITUTION Art. VI |

**Overall: feasible.** The two open risks (docking, trim drift) have cheap bench
experiments (Phase 9, ~$200) that retire them before any custom hardware.

## 2. How it steers — the wings decision

Brady wants wings, or something internal. Three real options from the research:

| Option | Prior art | Verdict |
|---|---|---|
| **Small slow propellers** (4× coreless, 45 mm) | GT-MAB, CERN blimp, every controllable micro-blimp | ✅ **v1 control.** Only option precise enough for docking; near-silent at blimp thrust levels (props run at ~20–30% of drone RPM) |
| **Flapping wings** | Cuddle-Fish (2 servos, 0.3–1.5 Hz, silent) | ⚠️ Beautiful, silent, weak — drift-control only; cannot hit a 15 cm dock throat. Servos themselves make noise |
| **Internal moving mass** | Cuddle-Fish pitch/altitude control | ✅ Good *add-on* for silent pitch/trim; cannot translate sideways alone |

**Decision: hybrid.** Propellers do the real flying (thrust vectoring for
up/down/forward/yaw). The body wears **wing-shaped soft fins** that provide
passive damping (research/04 §F — the pendulum oscillation damper) and *look*
like the creature is swimming. Later, a character-motion overlay can slowly flap
those fins for expression (servo-driven, decorative) while props do precision —
it looks like wings fly it; physics says props do. Internal moving mass is a v2
experiment for silent altitude trim. This is written into the sim's actuator
model so the software never has to change if actuators evolve.

## 3. What runs where

```
AIRCRAFT (later — ESP32-S3)          BASE STATION (now — your Mac)         DOCK (later)
├─ camera → MJPEG over WiFi          ├─ meemoo Python app (FastAPI)        ├─ guidance camera
├─ mic → audio stream                │  ├─ core: event bus, DB, config     ├─ electromagnet
├─ speaker ← TTS audio               │  ├─ perception (MediaPipe pose)     ├─ ring contacts + charger
├─ 4 props ← motor commands          │  ├─ voice (Moonshine→LLM→TTS)       ├─ load cell (trim)
├─ IMU + ToF → telemetry             │  ├─ brain (adapters, presets)       └─ IR beacons
└─ microWakeWord + "help" model      │  ├─ guardian (escalation SM)
                                     │  ├─ flight (SimulatedBlimp now)
   v1 STAND-INS:                     │  └─ dock (DockController)
   webcam = aircraft camera          ├─ React web app (Studio/Dashboard)
   laptop mic/speaker = voice        └─ SQLite + audit log
   2D sim = the aircraft
```

**The swap points** (why hardware arrives without rewrites): `VideoSource`
(webcam → `mjpeg_url`), audio I/O (server mic → satellite protocol),
`FlightController` (`SimulatedBlimp` → `MqttBlimp`), `DockController`
(simulated → serial). Only these four driver layers change. Everything above the
event bus never knows.

## 4. Test strategy (software → sky, in order)

1. **Unit tests** every phase (guardian + perception get the most).
2. **Sim with honest physics** — added mass, buoyancy drift, thrust saturation,
   drafts, funnel capture model. Docking controller must hit >95% in sim first.
3. **Bench** (Phase 9, no flying): noise, leak, magnet, capture-cone, dock-cam
   tracking — each experiment in docs/HARDWARE_MANUAL.md at beginner level.
4. **Tethered flight** — balloon on a light string, props live, in a draft-free
   room. Only after sim + bench pass.
5. **Free flight indoors** — HVAC off first, then on (draft rejection test).
6. **The demo script** (MASTER_PROMPT §demo) is the permanent end-to-end gate.

## 5. Execution system

- `docs/build-steps/step-NN.md` = one self-contained build prompt per phase.
- Run with **`/clear` then `/build-step NN`** — the command makes the fresh
  session read CONSTITUTION → TODO → the step file, build, verify, check off
  TODO items, commit, push, and update memory. Context is never lost because
  the repo docs ARE the context.
- Steps must run IN ORDER; each verifies its predecessor's gate before starting.
- A step that discovers a constitution conflict STOPS and asks Brady.
