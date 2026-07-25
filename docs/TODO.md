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
  - [x] Preliminary name screen run 2026-07-25 (TESS unreachable headless;
        via USPTO mirrors/aggregators — NOT a formal clearance). Findings:
        **"MEEMOO" is a LIVE registered US mark, Reg. 5547233 (SN 87536621),
        owner Tham Pash, registered 2018-08-21, toys/sporting-goods class** —
        real conflict risk for a cute companion robot (toys adjacency);
        also SN 98240802 "MEEMOO" (Shaoxing Chuyu Trading, fabrics class,
        filed 2023-10-25, status unverified); EU: "meemoo media in motion"
        EUTM 008258551 + meemoo.be = Flemish media-archive institute. No hit
        surfaced in robotics/software/health classes in this quick pass.
  - [ ] Formal attorney clearance (Classes 9/42/44 + toys-adjacency opinion
        vs Reg. 5547233) before any public launch — Brady + counsel
  - [ ] Register open domains (Brady): meemoo.io / heymeemoo.com / getmeemoo.com
        still showing OPEN as of 07-25 — grab before publicity
- [x] Python project: `pyproject.toml`, `meemoo/` package, ruff + mypy config,
      pytest scaffold, Makefile (`make dev`, `make test`, `make check`)
- [x] Web project: Vite + React + TS + Tailwind under `web/`, built assets served
      by FastAPI
- [x] `.env.example` with every variable documented; config loader (pydantic
      settings) that never crashes on missing optionals
- [x] CI: GitHub Actions — ruff, mypy, pytest, web typecheck+build
      (✅ VERIFIED 07-25: run 30164091952 completed green on push — Acuntel
      Actions billing block from 07-21 is no longer biting on this repo)

## Phase 1 — Core
- [x] Async pub/sub event bus (typed topics in core/topics.py, wildcard
      subscribe, replay-last for late subscribers, safe concurrent publishers)
      + unit tests (tests/test_bus.py)
- [x] SQLAlchemy models + migrations: devices, persons, contacts, provider_keys
      (encrypted), model_config, checkin_schedule, events (append-only),
      conversations, messages, alerts, usage, routes, waypoints, settings,
      **consent records (person-scoped, roommate/surrogate-ready), audit_log
      (append-only via SQLite triggers, tamper-evident sha256 hash chain +
      verify_audit_chain), memory_facts (structured per-person memory —
      NO biometric fields by design, test-enforced)** + dock_telemetry
      (load-cell/helium — Art. VII §5)
  - [x] Alembic revisions 0001+0002 in migrations/versions/ (standard format);
        `make migrate` applies them
  - [ ] ⚠️ Stock `alembic` CLI unusable: it hard-requires migrations/env.py and
        Brady's .env file-protection hook blocks creating any path matching
        ".env" (grep pattern also matches "…/env.py"). Runner
        meemoo/core/migrate.py (programmatic Alembic, same alembic_version
        table) covers upgrade; Brady: whitelist or create migrations/env.py
        himself to restore the CLI (content = standard env.py reading
        MEEMOO_DB_PATH; see meemoo/core/migrate.py docstring)
  - [ ] ⚠️ .env.example not updated (same hook): new optional var
        MEEMOO_FERNET_KEY_FILE (default data/fernet.key) — where the generated
        Fernet key lives when MEEMOO_FERNET_KEY is unset; Brady to add the line
- [x] Structured logging (JSON + human console), model/prompt/threshold version
      stamping on every escalation-relevant record (core/versioning.py registry
      + escalation_extra() log helper + version columns on audit_log/alerts)
- [x] Fernet encryption for provider keys (core/secrets.py: env key or
      generated 0600 key file); tests prove key material never in logs/repr
- Gate: ✅ 2026-07-25 `make check` ALL GREEN (ruff+mypy strict+34 pytest+web) —
  bus pub/sub/wildcard/replay/unsubscribe/concurrency covered; migration builds
  full schema; audit_log/events reject UPDATE+DELETE in tests

## Phase 2 — Perception (base-station camera = the detector)
- [x] Video ingest: `webcam` | `mjpeg_url` | `file` sources behind one interface
      (perception/video.py; cv2 lazy — package imports and tests run without it;
      live video needs `uv sync --group perception`)
- [x] Motion gate (frame-diff @ 3 fps) → MediaPipe Pose Full @ 15 fps when active;
      person never dropped from tracking by the motion gate once seen (pure
      `next_tier()` rule + tests; candidate path pins TRACKING even when occluded)
- [x] Signals: torso_angle, support_y, elevation vs calibrated floor line,
      v_descent, motion_energy, vis_frac (all torso-length-normalized; windowed
      MEDIAN baselines by frame-count so 5 fps sources stay under STILL_MOTION)
- [x] Floor-line + furniture-zone calibration with learning phase (YOLOv8n COCO
      bootstrap at install — lazy/optional ultralytics; reduced-sensitivity first
      7–14 days = non-ballistic candidates demoted to SOFT, ballistic stays hard;
      placement check refuses to arm without floor in lower third)
- [x] Fall state machine — **persistence-primary**: UPRIGHT → DESCENDING →
      GROUNDED_CANDIDATE → CONFIRMED_DOWN → VERIFYING → ESCALATE, plus LONG_LIE
      (with noise hysteresis) and VANISHED_DOWN parallel paths, CANDIDATE_SOFT
      for deliberate floor-sitters, ballistic-override of furniture suppression,
      RECOVERED + SNOOZED (voice-ok while still on floor; new ballistic re-arms)
- [x] `candidate.fall` at ~5 s (dispatch blimp), `person.down` at 15 s,
      `person.recovered`; thresholds committed as
      meemoo/perception/golden_thresholds.json (version-stamped via registry)
- [x] Thumbnails + rolling 60 s skeleton ring buffer (JSONL) per candidate event
      (thumbnail JPEG only when cv2 present; skeleton JSONL always)
- [x] Annotated frames (skeleton/bbox/state banner) published through FrameHub
  - [ ] /ws/video WebSocket endpoint consumes FrameHub — lands in Phase 7
        (per docs/build-steps/step-02.md §6)
- [x] Test fixtures + pytest: 3 spec scenarios, per-event recall asserted 100%
      at candidate stage on bundled fall clips, false-candidate rate per
      ADL-minute, time-to-candidate ≤ 6 s, person.down at 15±1 s, learning-phase
      + voice-ok/help/snooze units (121 tests green)
  - [ ] ⚠️ Bundled landmark JSONL is SYNTHETIC (20 clips, procedural stick-figure
        w/ honest §A.3 kinematics, expectations embedded in headers) — real
        GMDCSA-24 + CaucaFall extraction pending: run
        tests/fixtures/clips/fetch.py (~0.5 GB, gitignored) then
        tests/fixtures/extract_landmarks.py on a machine with
        `uv sync --group perception`; annotate floor_line/rest_zones/expect per
        clip before they join the assertion suite
- Gate: all perception tests green ✅ 2026-07-25 (`make check` ALL GREEN, 121
  pytest); fall/ADL/recovery replay verified headless via
  `python -m meemoo.perception.demo --landmarks <clip.jsonl>` (candidate.fall →
  person.down → person.recovered fire as specced)
  - [ ] live webcam annotated window on Brady's Mac: `uv sync --group
        perception` then `uv run python -m meemoo.perception.demo` (headless
        session can't open a camera/window — needs a human at the machine)

## Phase 3 — Voice (own-stack)
- [x] Audio I/O abstraction (voice/audio_io.py: MicSource/SpeakerSink via lazy
      sounddevice + Buffer/Collect/Null fakes; -15 dB partial ducking, never
      mute) + **MST/1 own framed satellite transport** (voice/transport.py:
      magic/version/type/seq/len/CRC32, 10 frame types, garbage-resilient
      incremental decoder — NOT Wyoming, spec in module docstring)
- [x] STT behind `STT` interface: MoonshineSTT primary + FasterWhisperSTT
      fallback (restoration-one pattern: int8 CPU, vad_filter, beam 1) — both
      lazy imports; factory degrades to None (text mode), never crashes
  - [ ] ⚠️ live-mic verification pending on Brady's Mac: `uv sync --group voice`
        (+ Moonshine is NOT on PyPI — install line in voice/stt.py docstring);
        Moonshine v2 *streaming* API + elderly-speech eval set still owed
- [x] TTS behind `TTS` interface: PocketTTS primary → PiperTTS floor → NullTTS
      (logs line + timed silence, keeps headless timing honest); 3 voice
      characters committed in voice/voices.py (elder_male/child/female with
      per-engine params)
  - [ ] ⚠️ Pocket-vs-Chatterbox 1-hour side-by-side listening NOT done (needs
        ears + hardware); all VoiceSpecs marked verified=False; Piper has no
        true child voice — amy@0.85 length_scale is the committed floor approx
  - [ ] Piper voice downloads on Brady's Mac: `uv run python -m
        piper.download_voices en_GB-alan-medium en_US-amy-medium
        en_US-lessac-medium --data-dir data/voices`
- [x] VAD behind interface: SileroVAD (lazy pysilero-vad, ONNX no-torch) +
      adaptive EnergyVAD pure-python floor; SilenceEndpointer with
      elderly-pause-tolerant 1.0 s end-of-turn; `partial()` on the STT interface
  - [ ] smart-turn v3 semantic endpointing not integrated (model download story
        pending) — SilenceEndpointer is the honest stand-in behind the same API
  - [ ] pipeline does not yet publish `utterance.partial` (needs live streaming
        STT; topic reserved in core/topics.py)
- [x] **Distress detector (voice/distress.py + voice/phrases.py): pure-stdlib
      fuzzy phrase match (token Levenshtein ≤1) on EVERY final transcript,
      publishes `utterance.distress` + deterministic spoken ack — no LLM, no
      network, brain provably never called; pytest proves the bypass with all
      API keys absent AND socket connects monkeypatched to raise**
- [x] Wake word: `WakeWord` interface — PushToTalk v1 trigger + lazy
      OpenWakeWord (stock model); custom "hey meemoo" model = hardware-phase
      (1–2 wk training per maintainers); distress detector architecturally
      separate from wake (Art. IV §5)
- [x] Conversation sessions (voice/session.py): rolling 40-msg context, 45 s
      silence close via injectable clock, transcript storage default ON with
      per-device `Device.store_transcripts` toggle (OFF ⇒ not even a
      Conversation row), raw audio buffer cleared + logged post-STT — no audio
      field exists anywhere in the session/message path
- [x] Spoken AI disclosure at session start + 600 s periodic re-disclosure +
      deterministic "are you real?" answer + 988 crisis protocol
      (voice/crisis.py: fixed template response, `utterance.crisis` published,
      escalation-version-stamped logging) — all template text, no model
- [x] Barge-in scaffolding: mic ducking hooks around playback + always-on
      "stop" detector halts playback independent of AEC (research 02 §D.3);
      full AEC = hardware phase
- Gate: ✅ 2026-07-25 headless — `make check` ALL GREEN (230 pytest, 109 voice);
  `make demo-voice` / `python -m meemoo.voice.demo --voices-check` speaks the
  3 characters + logs measured TTFA per reply; `--say "help me"` shows the
  bypass firing; distress tests green offline (keys absent + network dead)
  - [ ] live mic→speaker run on Brady's Mac (headless session has no audio
        hardware): `uv sync --group voice`, download Piper voices, then
        `make demo-voice` — verify audible replies in all 3 voices and
        TTFA < 2 s with a real STT engine loaded

## Phase 4 — Brain
- [x] Provider adapter interface `complete(messages, model, max_tokens,
      system=)` + streaming variant (brain/types.py); adapters one file each in
      brain/providers/: Anthropic (official SDK, lazy; refusal handled before
      content; server-side `fallbacks: "default"` opted in on opus-5/fable-5;
      real token streaming), OpenAI (SDK, lazy), Google (google-genai, lazy),
      Ollama (stdlib HTTP against OLLAMA_URL — the first-class offline brain);
      fifth provider = one new file, PROVEN twice (fake.py ships as the fifth;
      tests also inject a synthetic sixth module and the factory just works)
  - [ ] ⚠️ adapters verified against stubbed SDK/HTTP in tests (request shape,
        response/usage parsing, refusal) — LIVE run with real keys pending on
        Brady's Mac: `uv sync --group brain` then
        `uv run python -m meemoo.brain.demo` with ANTHROPIC_API_KEY (and/or
        `--provider ollama --model llama3.2` with Ollama running)
  - [ ] streaming is real for Anthropic; other adapters use the default
        single-chunk stream() until live streaming is needed
- [x] Tier routing (brain/router.py): task type → reflex/conversation/reasoning;
      per-device model_config rows override defaults (haiku-4.5 / sonnet-5 /
      opus-5 = the spec's cheap/mid/strong); Art. IV note enforced in
      architecture — brain publishes NO escalation topics, LLM never gates
      escalation. Cost meter (brain/usage.py): per-request usage rows + daily
      aggregate; versioned pricing table
  - [ ] ⚠️ OpenAI/Google pricing entries are ESTIMATES (Anthropic rows are
        first-party rates) — owner should verify before trusting the meter
        across vendors
- [x] Personality assembly (brain/personality.py): base template (short
      spoken-length replies, TTS-safe) + preset role/personality + owner custom
      context + device context (name/reminders/mode/room) + memory facts;
      prompt version registered in the escalation-record registry
- [x] **Preset library** (brain/presets/*.yaml + loader): companion, trainer
      (hardcore / encouraging / keeps_it_simple), hospital_checkin (no-ranking
      language baked in per Art. IV §2), tour_guide, tutor — versioned YAML,
      raw-editable
- [x] Memory (brain/memory.py): post-conversation extraction into memory_facts
      via reflex tier (strict JSON, category whitelist, biometric-token facts
      DROPPED in code per Art. V §1) + mood-note onto the conversation row;
      no provider ⇒ graceful skip
- [x] Scripted no-API-key fallback (brain/scripted.py): greeting → "are you
      feeling alright?" → branch → reminder → close; zero keys/network; the
      engine degrades to it on missing provider AND on provider failure
- [x] Medical-question refusal-and-handoff rail (brain/medical.py):
      deterministic regex detector runs BEFORE any model; fixed handoff
      template (tests prove the model is never consulted). Anti-repetition
      paraphrase bank (brain/paraphrase.py): 10+ variants per intent, sampled
      without replacement in a window, repetition-rate metric logged; Fasola
      continuity lines (name at greet/farewell, last-session reference,
      next-check-in forward reference)
- [x] Engine (brain/engine.py): ConversationBrain callable drops into
      VoicePipeline(brain=…) — wired in voice/demo.py; refusal ⇒ deterministic
      warm line; rolling 40-msg context; preset switch at runtime
- Gate: ✅ 2026-07-25 — same check-in conversation through the REAL Anthropic
  adapter (stubbed SDK), REAL Ollama adapter (stubbed local HTTP), and
  scripted fallback purely by model_config flip; system prompt byte-identical
  across providers (tests/brain/test_engine.py); cost meter accumulates
  per-request rows + daily total; `--compare-presets` shows encouraging vs
  hardcore trainer tone flip; repetition rate printed by
  `make demo-brain` (293 pytest green — 63 brain, `make check` ALL GREEN)
  - [ ] live-provider gate run on Brady's Mac (real key / local Ollama) — see
        the adapter sub-item above

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
