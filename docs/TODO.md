# Meemoo — Build TODO

> Created 2026-07-25 after the constitution. Phases execute in order; within a
> phase, items are roughly ordered. Every phase ends with its gate passing.
> Mark items `[x]` as they land; keep this file current — it is the build's
> source of truth across sessions.

## Phase 0 — Project scaffold
- [x] Rename: **Meemoo** locked 2026-07-25 — repo now Acuntel/meemoo, local
      folder ~/dev/meemoo, living docs renamed; wake word = "Hey Meemoo"
- [ ] Formal USPTO trademark screen for "Meemoo" (robotics/health classes) +
      register domains (meemoo.io OPEN, heymeemoo.com OPEN, getmeemoo.com OPEN
      as of 2026-07-25; meemoo.com parked-for-sale aftermarket; meemoo.ai taken
      2025-07-27)
- [ ] Python project: `pyproject.toml`, `meemoo/` package, ruff + mypy config,
      pytest scaffold, Makefile (`make dev`, `make test`, `make check`)
- [ ] Web project: Vite + React + TS + Tailwind under `web/`, built assets served
      by FastAPI
- [ ] `.env.example` with every variable documented; config loader (pydantic
      settings) that never crashes on missing optionals
- [ ] CI: GitHub Actions — ruff, mypy, pytest, web typecheck+build
      (⚠️ check Acuntel Actions billing status first — was blocked 07-21)

## Phase 1 — Core
- [ ] Async pub/sub event bus (typed topics, wildcard subscribe, replay-last for
      late subscribers) + unit tests
- [ ] SQLAlchemy models + migrations: devices, persons, contacts, provider_keys
      (encrypted), model_config, checkin_schedule, events (append-only), 
      conversations, messages, alerts, usage, routes, waypoints, settings,
      **consent records (person-scoped, roommate/surrogate-ready), audit_log
      (append-only, tamper-evident), memory_facts (structured per-person memory:
      names, preferences, workout history — NO biometric fields by design)**
- [ ] Structured logging (JSON + human console), model/prompt/threshold version
      stamping on every escalation-relevant record
- [ ] Fernet encryption for provider keys; never logged
- Gate: `pytest` green; bus + models covered

## Phase 2 — Perception (base-station camera = the detector)
- [ ] Video ingest: `webcam` | `mjpeg_url` | `file` sources behind one interface
- [ ] Motion gate (frame-diff @ 3 fps) → MediaPipe Pose Full @ 15 fps when active;
      person never dropped from tracking by the motion gate once seen
- [ ] Signals: torso_angle, support_y, elevation vs calibrated floor line,
      v_descent, motion_energy, vis_frac (all torso-length-normalized)
- [ ] Floor-line + furniture-zone calibration with learning phase (YOLOv8n COCO
      bootstrap at install; reduced-sensitivity first 7–14 days, user-visible)
- [ ] Fall state machine — **persistence-primary**: UPRIGHT → DESCENDING →
      GROUNDED_CANDIDATE → CONFIRMED_DOWN → VERIFYING → ESCALATE, plus LONG_LIE
      and VANISHED_DOWN parallel paths, CANDIDATE_SOFT for deliberate
      floor-sitters, ballistic-override of furniture suppression, RECOVERED
- [ ] `candidate.fall` at ~5 s (dispatch blimp), `person.down` at 15 s,
      `person.recovered`
- [ ] Thumbnails + rolling 60 s skeleton ring buffer (JSONL) per candidate event
- [ ] Annotated live feed over WebSocket
- [ ] Test fixtures: GMDCSA-24 + CaucaFall → extract landmark JSONL (committed),
      fetch script for raw clips (gitignored); pytest against the 3 spec
      scenarios with per-event recall asserted at 100% on bundled fall clips
- Gate: all perception tests green; live annotated webcam view works

## Phase 3 — Voice (own-stack)
- [ ] Audio I/O abstraction (server mic/speaker now; blimp satellite later; own
      framed transport protocol ~200 lines)
- [ ] STT: Moonshine v2 Streaming behind an `STT` interface (faster-whisper as
      alternate impl — we already have working code from restoration-one)
- [ ] TTS: Pocket TTS or Chatterbox behind a `TTS` interface; Piper as offline
      floor; 3 voice characters (older man / child / female) selectable per device
- [ ] Silero VAD + smart-turn endpointing; partial-transcript streaming
- [ ] **Distress detector: local keyword/intent check for "help me / I need help /
      call someone / emergency" on EVERY utterance — no LLM, no network; fires
      Guardian directly** + pytest proving the bypass
- [ ] Wake word: openWakeWord (dev) behind a `WakeWord` interface; push-to-talk
      in UI as v1 trigger; "Hey <name>" model training deferred until rename
- [ ] Conversation sessions (rolling context, 45 s silence close), transcript
      storage default ON with per-device toggle; raw audio discarded post-STT
- [ ] Spoken AI disclosure at session start + periodic reminder + 988 crisis
      protocol path (deterministic, logged)
- [ ] Barge-in not required, not architected out (ducking hooks in place)
- Gate: mic → text → (echo brain) → speech loop < 2 s on the MacBook; distress
  bypass test green with network disabled

## Phase 4 — Brain
- [ ] Provider adapter interface `complete(messages, model, max_tokens)`;
      adapters: Anthropic, OpenAI, Google, Ollama — one file each, fifth provider
      = one new file
- [ ] Tier routing (reflex / conversation / reasoning) by task type; per-request
      + per-day token/cost logging → cost meter
- [ ] Personality assembly: base template (short spoken-length replies) + preset
      role/personality + owner custom context + device context (person's name,
      reminders, mode) + structured memory facts
- [ ] **Preset library**: 5 roles × personality sub-presets (Trainer: hardcore /
      encouraging / keeps-it-simple; Hospital Check-in; Companion; Tour Guide;
      Tutor) as versioned YAML — editable raw context for power users
- [ ] Memory: post-conversation fact extraction into memory_facts (explicit,
      inspectable, deletable — names/workouts/preferences; NO biometrics);
      mood-note summary per conversation
- [ ] Scripted no-API-key fallback: templated check-in dialogue; safety loop
      never depends on a third party
- [ ] Medical-question refusal-and-handoff rail; anti-repetition paraphrase bank
      with logged repetition rate
- Gate: same conversation runs on Anthropic, Ollama, and scripted fallback by
  flipping config; cost meter moves

## Phase 5 — Guardian (most tests)
- [ ] Escalation state machine exactly per spec (IDLE → CHECK_IN_DUE → CHECKING →
      OK/NO_RESPONSE → CONCERN → verify → ESCALATE_L1 → L2 → L3) as a pure,
      fully-tested module; person.down enters CONCERN from any state
- [ ] L3 = ring configured test number + full-screen alert; auto-911 gated OFF
      behind a config flag that ships off (documented TODO)
- [ ] Contacts (ordered, prefs), acknowledgment from dashboard halts escalation
      (+ Twilio SMS reply when creds exist)
- [ ] Check-in scheduler (APScheduler): default 9a/1p/6p/9p; check-in = sim round
      + real voice check-in
- [ ] Notifier adapter: Twilio impl (demo) + simulated-call UI impl; own-telephony
      replacement documented as a roadmap item
- [ ] Immutable audit rows for every transition w/ evidence links; false-alarm
      counter surfaced
- [ ] pytest: full state walk, "help me" bypass, ack halting, timeout ladders,
      no-response → L2 → L3
- Gate: guardian test suite green; simulated end-to-end fall → L1 → ack works

## Phase 6 — Flight + dock sim (honest physics)
- [ ] `FlightController` interface per spec + `DockController` sibling
      (setRetention, setChargeEnabled, capture confirmation via two signals)
- [ ] `SimulatedBlimp`: 2D floor plan (JSON rooms; default apartment + facility
      wing), floaty easing, battery drain/charge, auto-return <25%,
      **added-mass inertia, ±5 gf randomized buoyancy drift, thrust saturation
      ~10 gf/motor, HVAC draft fields, funnel capture model (R_capture, v_max)**
- [ ] Docking state machine: FLYING → DOCK_REQUESTED → TRANSIT → ALIGN →
      FINAL_APPROACH → CAPTURE_PENDING → CAPTURED → CHARGING → RELEASE →
      DEPARTED, with ABORT/retry + DOCK_FAILED
- [ ] Telemetry: netBuoyancy_gf from hover thrust duty; helium_level decay +
      top-off; dock load-cell field in the data model
- [ ] `MqttBlimp` stub with full protocol spec in comments (updated constants:
      65 g payload, 120 L sphere, negative trim, ESP32-S3 + XIAO Sense)
- [ ] Sim round + waypoints; during person waypoint, Guardian runs REAL voice
      check-in (sim is fake; check-in is real)
- [ ] pytest: docking succeeds >95% across randomized buoyancy/draft episodes;
      capture never confirmed on single signal
- Gate: whale docks reliably in sim with honest physics

## Phase 7 — API + Web
- [ ] REST CRUD `/api/v1/...` for all tables; OpenAPI docs work
- [ ] WebSockets: /ws/video, /ws/sim, /ws/events, /ws/voice (browser PTT)
- [ ] **Setup Studio**: chat-style config (LLM extracts structured config from
      plain language → review/edit → save), preset role picker + personality
      sub-presets, voice selection with audio preview, provider/key management
      (managed-mode default framing; BYO = advanced), cost readout, privacy
      toggles, activity modes
- [ ] **Family Dashboard**: Today timeline w/ mood notes, Live View (sim +
      annotated feed + battery/dock), Alerts w/ Acknowledge + evidence, History
      + cost meter; warm calm design (worried-daughter-at-11pm bar)
- [ ] **Research-credibility layer**: engagement trajectory (user-initiated share
      over time), adherence w/ prompts-required, false-alarms/week headline,
      human-contact tracking, abandonment early-warning composite, data export
      (CSV), synthetic-data demo mode (clearly labeled)
- [ ] Simulated incoming-call screen for credential-less escalation demo
- Gate: full demo script steps 1–6 pass end-to-end on the MacBook

## Phase 8 — Integration hardening
- [ ] Run the demo script cold from `make dev` on a clean checkout; fix breaks
- [ ] Graceful-degradation matrix test: no API key / no camera / no mic / no sim
      — nothing crashes
- [ ] README: 5-min quickstart, architecture diagram, MQTT handoff spec,
      fake-vs-real table
- [ ] Layout smoke per Brady's UI-push rule before any deploy

## Phase 9 — Hardware bench (parallel track, ~$200)
- [ ] Order docs/ORDER_LIST.md parts
- [ ] Noise: motor+prop on the bench → SPL @ 1 m (validate the 35–45 dB estimate)
- [ ] Leak: 36" balloon lift vs days on the 0.1 g scale (validate 0.3–0.6 g/day)
- [ ] **The 20-minute test that decides funnel-vs-winch:** ballasted-neutral
      balloon, hand-pushed nose-first into a cone — does held thrust center it or
      does it stall on the wall?
- [ ] Electromagnet hold-through-HVAC-cycle + clean-release (+ reverse pulse?)
- [ ] Dock-camera tracking loop vs balloon-on-a-string: ≥20 Hz, ~1 cm lateral,
      3 lighting conditions
- [ ] Speaker intelligibility check at 1–2 m with an older listener if available

## Phase 10 — 3D sim investigation (Brady-requested)
- [ ] Evaluate NVIDIA Isaac Sim for blimp+dock physics (needs RTX GPU — cloud
      path: AWS g6/g5 instance or NVIDIA Brev; Brady has NVIDIA API relationships)
- [ ] If viable: model the sphere w/ added mass + drafts, train/tune the docking
      controller in 3D, keep the 2D sim as product UI
- [ ] Decision memo: is Isaac worth it vs. upgrading our own sim to 2.5D

## Phase 11 — Go-live gates (BLOCKING before any real user)
- [ ] Everything in Constitution Article VI §2, checked off with dates
