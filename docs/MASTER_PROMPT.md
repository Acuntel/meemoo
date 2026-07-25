# MASTER PROMPT: Build "Helpee" — The Complete Software Platform for a Floating Companion Robot

> **Naming note (2026-07-25):** The spec below was originally drafted under the codename
> "Drift". Brady's current working name is **Helpee** (not final). Everywhere the spec
> says Drift, read Helpee. Package/module names in code use `helpee`.

---

You are building the complete software platform for a hardware product that does not physically exist yet. Read this entire spec before writing any code. Build it as one working system, not a collection of stubs.

## What the product is

A small, cute, animal-shaped helium blimp (whale, seal, manta ray) that floats quietly at eye level and serves as a companion for older adults living alone, and does rounds in nursing homes and hospitals. It checks in on people, holds conversations, gives reminders, can coach someone through a workout or guide a tour, and escalates to family, facility staff, or emergency services when someone asks for help or the system detects a possible problem (like a person on the floor who isn't responding). It is a presence and safety device, not a task robot. It is deliberately non-threatening and childlike in personality.

The critical architecture decision: the aircraft is dumb, the ground is smart. The blimp carries only a camera, microphone, speaker, and small steering motors (about 150 grams of payload). Every piece of intelligence lives in a wall-powered base station. The blimp flies short 10 to 20 minute rounds and lands itself on a funnel-shaped charging dock between them. Emergency calls route through the base station's connection, never through the aircraft.

Because the hardware doesn't exist yet, YOU ARE BUILDING THE ENTIRE BRAIN AGAINST STAND-INS: the laptop webcam and microphone act as the blimp's camera and mic, and a 2D simulator acts as the aircraft. The system must be architected so that when real hardware arrives, only the input/output drivers get swapped and everything else keeps working unchanged.

## Product principles (these resolve all ambiguity)

1. The person being cared for is the user; their adult child or facility staff is the customer. Both get interfaces.
2. Local-first. Vision and wake-word processing happen on-device. Video never leaves the machine except as short event clips the customer explicitly enables. Privacy is a feature.
3. Model-agnostic brain. The owner plugs in their own AI provider API key and chooses which models power the device. This is the product's core differentiator. No hardcoded dependence on any single AI company.
4. Graceful degradation everywhere. No API key configured? Conversation falls back to scripted check-ins. Camera unavailable? Voice-only mode. Simulator not running? Everything else still works. The system never crashes because one input is missing.
5. Everything observable. Every check-in, detection, escalation, and flight is logged and visible in the dashboard.

## Tech stack (use exactly this)

- Backend: Python 3.11+, FastAPI, WebSockets for real-time, SQLite via SQLAlchemy for storage, APScheduler for scheduled rounds
- Vision: OpenCV + MediaPipe Pose for person detection and fall detection (runs on CPU, no GPU assumed)
- Speech: faster-whisper (small model) for speech-to-text, Piper for text-to-speech, both fully local. openwakeword for wake word if practical; otherwise push-to-talk in the UI as the trigger, with the wake word behind an interface for later
- Frontend: React + Vite + Tailwind, single-page app served by FastAPI
- Calls/SMS: Twilio (behind an adapter; if no Twilio credentials, log the escalation and simulate the call in the UI with a fake incoming-call screen)
- Everything runs with `docker compose up` OR a single `make dev` on a laptop. Target: also runs on Raspberry Pi 5, so keep dependencies CPU-friendly

## System architecture (build these as separate modules with clean interfaces)

```
/helpee
  /core          # event bus, config, database models, logging
  /perception    # video ingest, person detection, fall detection
  /voice         # STT, TTS, wake word interface, conversation session manager
  /brain         # model-agnostic LLM layer, routing, personality, context
  /guardian      # check-in scheduler, escalation state machine, contacts
  /flight        # hardware abstraction: simulator now, real blimp later
  /fleet         # device registry, per-device config (built for N devices even though v1 runs 1)
  /api           # FastAPI routes + WebSocket endpoints
  /web           # React app: Setup Studio, Family Dashboard, Live View, Sim
```

Modules communicate through an internal async event bus (simple pub/sub). Perception publishes `person.detected`, `person.down`, `person.unresponsive`. Guardian subscribes and drives escalation. Voice publishes `utterance.heard`. Brain subscribes and responds. Nothing imports another module's internals directly. This is what makes the hardware swap possible later.

## Module specs

### 1. Perception (the eyes)

- Ingest video from a configurable source: `webcam` (default), `mjpeg_url` (this is how the future ESP32-CAM on the blimp connects), or `file` (for testing with recorded clips)
- Person detection and pose estimation via MediaPipe on every Nth frame (configurable, default 5) to keep CPU sane
- Fall detection heuristic: person's pose transitions to horizontal near floor level AND remains there for a configurable window (default 15 seconds) without significant movement. Emit `person.down` on detection, `person.recovered` if they get up
- Presence tracking: is a person visible, how long, last seen timestamp
- Every detection event stores a thumbnail frame (locally) with timestamp for the dashboard timeline
- Expose a live annotated video feed (bounding boxes, pose skeleton, state label) over WebSocket to the dashboard's Live View
- Tune for recall over precision on falls: a false alarm asks "are you okay?"; a miss is the catastrophic failure mode

### 2. Voice (the ears and mouth)

- Full loop: audio in → faster-whisper STT → brain → Piper TTS → audio out
- Conversation sessions: a session opens on wake word or check-in initiation, holds rolling transcript context, closes after configurable silence (default 45 seconds)
- Two voices to include: a default warm/friendly one, and make voice selectable in config
- Barge-in not required for v1, but do not architect it out
- Every conversation is transcribed and stored, viewable in the dashboard, with a per-device toggle to disable transcript storage (privacy)
- CRITICAL SAFETY BEHAVIOR: the phrase-level intent "help me / I need help / call someone / emergency" detected in ANY utterance immediately triggers the Guardian escalation flow, bypassing the LLM entirely. This must be a local keyword/intent check that works even with no API key and no internet

### 3. Brain (model-agnostic intelligence — the core differentiator)

- Provider adapter interface: `complete(messages, model, max_tokens) -> response`. Ship four adapters: Anthropic, OpenAI, Google, and Ollama (local). Adding a fifth provider must require only one new file
- API keys entered by the owner in the web UI, stored encrypted at rest in SQLite, never logged
- Tiered routing: each device config maps three tiers to provider+model choices:
  - `tier.reflex` (cheap/fast): routine check-in chat, reminders, simple Q&A
  - `tier.conversation` (mid): open-ended companionship conversation
  - `tier.reasoning` (strong): ambiguous situations, e.g. deciding whether a scene description + transcript warrants escalation
- The router picks the tier by task type, so simple jobs never burn expensive tokens. Log tokens used per request and per day per device, surfaced in the dashboard as an estimated cost meter
- Personality layer: system prompt assembled from (a) a base personality template — warm, gentle, patient, a little playful, never condescending, short spoken-length replies since output is TTS, (b) the owner's custom instructions from the Setup Studio, (c) device context: person's name, medication reminder schedule, facility vs home mode, current activity mode
- Activity modes that change the system prompt and behavior: `companion` (default), `trainer` (counts reps verbally, encourages, references what the camera sees), `tour_guide` (location script loaded from config), `tutor` (adapts to the chosen model's ability)
- If no API key is configured: scripted fallback mode with templated check-in dialogue ("Good morning, just checking in. Are you feeling alright today?") so the safety loop never depends on a third party

### 4. Guardian (the safety spine — highest-stakes module, most tests)

Escalation state machine, explicit states, fully logged transitions:

```
IDLE → CHECK_IN_DUE → CHECKING (voice check-in active)
CHECKING → OK (person responded fine) → IDLE
CHECKING → NO_RESPONSE (timeout) → CONCERN
person.down event from ANY state → CONCERN
CONCERN → verify: fly to person (sim), ask "are you okay?" twice
CONCERN → OK (responds fine) → IDLE, log the event
CONCERN → ESCALATE_L1: notify family contacts (Twilio SMS + call, or simulated)
ESCALATE_L1 → no acknowledgment in N minutes → ESCALATE_L2: facility staff webhook / next contacts
ESCALATE_L2 → no acknowledgment → ESCALATE_L3: flagged for emergency services
```

- L3 NEVER auto-dials 911 in this build. It rings the configured test number and displays a full-screen alert. Real emergency dialing is a documented TODO gated behind an explicit config flag that ships off
- Contacts: ordered list per device with name, relationship, phone, notification prefs
- Check-in schedule: configurable times per device (default 9am, 1pm, 6pm, 9pm). A scheduled check-in launches a round (flight to the person in sim) plus a voice check-in
- Acknowledgment: a contact can acknowledge an alert from the dashboard (and via Twilio SMS reply if real credentials exist), which halts escalation
- Every state transition is an immutable audit log row: timestamp, trigger, evidence link (thumbnail/transcript). This is the liability record; treat it like a flight recorder

### 5. Flight (hardware abstraction + simulator)

- `FlightController` interface: `takeoff()`, `land()`, `goto(waypoint)`, `patrol(route)`, `hold()`, `return_to_dock()`, `battery_status()`, `position()`
- v1 implementation: `SimulatedBlimp` — a 2D top-down floor plan (simple JSON-defined rooms and dock location, ship a default apartment and a default facility wing) rendered in the web UI. The blimp is a cute whale sprite that drifts between waypoints with gentle floaty easing, not robotic straight lines. Battery drains in flight (20 min full to empty), recharges on dock, auto-returns below 25%
- Rounds: a route of waypoints (resident rooms / areas). During a sim round at a person waypoint, Guardian runs the real voice check-in through the real mic and speaker. The sim is fake; the check-in is real
- Second implementation stub: `MqttBlimp` — full protocol spec documented in code comments (topics for telemetry, commands, video URL handoff) targeting a future ESP32 payload, methods raise NotImplemented with the spec attached
- The dock in sim also exposes `helium_level` decaying a few percent per week with a "top-off" button, because refill state is part of the future subscription and belongs in the data model now

### 6. Fleet + Setup Studio (the owner-facing product)

- Device registry: v1 runs one device but every table and API is keyed by `device_id`. A facility running 20 blimps is the same software
- Setup Studio, the flagship UI: a chat-style configuration experience that looks and feels like a modern AI chat interface, where the owner literally tells the device what it should be in plain language ("You're checking on my mom Ruth, she takes her heart medication at 8am and 8pm, she loves gardening and talking about her grandkids, be gentle, call me first if anything seems wrong")
- The Studio runs this through the configured model to extract structured config (name, reminders, interests, tone, escalation contacts) AND stores the raw instructions as the device's custom context. Show the extracted config for review and editing before saving. This is "prompting your robot" as a first-class product experience
- Also in the Studio: provider/API key management, model tier assignment with a live estimated monthly cost readout, voice selection, activity mode toggles, privacy toggles

### 7. Family Dashboard (the customer-facing product)

- Today view: check-in results as a timeline (time, mood note the brain writes after each conversation, one-tap "listen to summary")
- Live View: current sim position, battery, dock status, and the annotated camera feed
- Alerts: active and historical escalations with evidence and an Acknowledge button
- History: rounds completed, conversations (if storage enabled), detections, cost meter
- Warm and calm visual design. This is looked at by a worried daughter at 11pm; it should reduce anxiety, not induce it. Soft colors, rounded, generous whitespace, zero jargon

## Data model (SQLite, minimum tables)

`devices`, `persons` (cared-for people, per device), `contacts` (ordered, per device), `provider_keys` (encrypted), `model_config` (tier mappings per device), `checkin_schedule`, `events` (append-only: detections, transitions, flights; typed, indexed by device+time), `conversations` + `messages`, `alerts` (state, acknowledgments), `usage` (tokens/cost per request), `routes` + `waypoints`, `settings`

## API surface (FastAPI)

REST for CRUD on all of the above under `/api/v1/...`, WebSockets: `/ws/video` (annotated frames), `/ws/sim` (blimp position/battery), `/ws/events` (live event stream for dashboard), `/ws/voice` (push-to-talk audio from browser when not using server mic). Auto-generated OpenAPI docs must work.

## The demo script (build the system so this exact flow works end-to-end)

1. `make dev` → open browser → Setup Studio → type instructions about "Ruth" → review extracted config → save → paste an Anthropic API key (or skip, hitting scripted fallback)
2. Dashboard shows the whale on its dock, floor plan loaded, next check-in scheduled
3. Click "Run round now" → whale drifts through the sim apartment → arrives at Ruth's waypoint → real audio: it greets Ruth by name through the speakers, listens through the mic, has a genuine short conversation, reminds about medication → returns to dock → dashboard timeline gains an entry with a mood summary
4. Tester lies on the floor in webcam view and stays still → within the window, `person.down` fires → whale flies over in sim → "Ruth, are you okay?" twice through the speakers → no response → CONCERN → ESCALATE_L1 → simulated call screen pops (or the tester's real phone rings via Twilio) → tester clicks Acknowledge → escalation halts, full audit trail visible
5. Say "help me" out loud mid-conversation at any point → immediate escalation, no LLM in the path
6. Switch the conversation tier from one provider to another in the Studio → next check-in runs on the new model → cost meter reflects it

## Quality bar

- Guardian state machine and the fall-detection heuristic get real pytest coverage, including the "help me" bypass and acknowledgment halting escalation. Perception tests run against 3 short bundled test clips (person walking, person falling, empty room) — generate or source these
- README with 5-minute quickstart, architecture diagram, the MQTT hardware handoff spec, and a "what is fake vs real" table
- Type hints throughout, no bare exceptions, structured logging
- .env.example with every variable documented. Missing optional credentials must never crash startup

## What NOT to build

No auth/multi-tenant login (single-owner local deployment), no payment processing (cost meter only; the credits-resale business model is future work), no real 911 integration, no cloud deployment configs, no mobile apps (responsive web only), no actual flight firmware. Do not stub the core loops though: perception, voice, brain, guardian, and sim must genuinely work.

Build the whole thing. Start with core + the event bus, then perception, then voice, then brain, then guardian, then flight sim, then the web app, wiring the demo script as you go. When done, run through the demo script yourself and fix whatever breaks before declaring it finished.

---

## Brady's additional directives (from the kickoff message, 2026-07-25)

1. Deep research FIRST: competitors, where Helpee stands out, how the charging
   dock + autonomous landing actually work, size target ("two average balloons
   combined" — validate against physics), near-silent flight, medical-device
   requirements, bump/balance recovery.
2. After research: ask Brady as many questions as possible about what he's missing.
3. Then write the project CONSTITUTION (what it must be, what we must work around).
4. Then the full to-do list of every application/piece of code to build and test.
5. Then execute step by step until done.
6. Reuse past code where useful — known candidates: restoration-one
   `whisper-service/` (faster-whisper FastAPI), Paradise call bot (Twilio +
   ElevenLabs calling), `~/.dictation` (VAD + anti-hallucination lessons).
7. Repo: its own GitHub repo (Acuntel org).
8. **OWN THE ENTIRE TECH STACK (constitution principle, added 2026-07-25):**
   Build as much of the stack ourselves as possible — including voice. Default
   to building the industry-standard capability in-house. A third-party
   component is allowed ONLY if (a) it is significantly better than what we can
   build, or (b) we tried and genuinely can't make ours work — and even then it
   sits behind our own adapter interface so it can be replaced later. Open
   models/weights we run ourselves (whisper, Piper, MediaPipe) count as "ours";
   hosted third-party APIs do not.
