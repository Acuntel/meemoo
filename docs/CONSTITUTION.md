# The Meemoo Constitution

> Ratified 2026-07-25 from Brady's decisions on the research question list.
> **The name is MEEMOO** — locked by Brady 2026-07-25 (naming history:
> "Drift" in the original spec → "Helpee" working codename → Meemoo). Historical
> research reports in docs/research/ still say Helpee; they are archival.
> Wake word: "Hey Meemoo" — vowel-heavy (survives presbycusis), no collision
> with the "help" distress word. Pending: formal USPTO/trademark screen (Phase 0).
> This document is binding on every future build session. When a feature request
> conflicts with an Article, the Article wins unless Brady amends it here.

## Preamble — what this is

A small, cute, **round** floating companion robot: a helium sphere that drifts at
eye level, checks in on people, holds conversations, remembers them, coaches and
comforts them, and gets help when something looks wrong. The aircraft is dumb; the
ground is smart. **Hospital-grade by design, home-simple by default.** We own the
stack. We ship safety as architecture, not promises.

---

## Article I — Form & identity

1. **The body is circular.** A sphere (or near-sphere with a cute tail/fins) is the
   PRIMARY form target — Brady's explicit call. Physics supports it: a sphere has
   the minimum envelope area per liter (lightest skin per unit of lift), and
   precedent exists (Aerotain Skye was spherical; GT-MAB is a rounded saucer).
   Trade-off accepted: a sphere lacks passive yaw/translation damping — small soft
   fins/tail (which double as the character's tail) plus active swing damping
   compensate. Only if flight testing proves a sphere uncontrollable do we fall
   back toward an ellipsoid — and then the roundest one that flies.
2. **v1 physical target:** ~120 L sphere ≈ **0.61 m diameter**, ~65 g payload
   (30% margin over the ~50 g BOM), trimmed **2–4 g negatively buoyant**.
   Sim constants use these numbers.
3. Character: soft, childlike, non-threatening. Fully stylized — never mix
   realistic features (pupils, snouts) into an abstract body (uncanny-valley
   evidence, HRI 2020). Expressive channels at close range are light, motion, and
   sound — not a face.
4. Envelope: metallized film (latex banned in hospitals; mylar explicitly
   approved). Soft-touch sleeve on the lower third where hands touch. The
   plush bladder-in-shell skin is the v2 body (needs ~300 L).

## Article II — Architecture invariants

1. **Dumb aircraft, smart ground.** The aircraft carries sensors, speaker, motors,
   radio — never intelligence. All perception, planning, and speech processing run
   on the wall-powered base station.
2. Modules communicate ONLY over the internal event bus. No module imports
   another's internals. This is what makes the hardware swap possible.
3. **The dock is its own device** (`DockController` beside `FlightController`):
   guidance camera, electromagnet retention, concentric-ring charging, load cell,
   future helium top-off valve. Capture is confirmed by TWO independent signals
   (contact continuity + hall/reed switch), never vision alone.
4. **The simulator tells the truth.** It models added-mass inertia (~2× effective
   mass), drifting buoyancy (±5 gf, randomized), single-digit-gram thrust
   saturation, funnel capture radius/speed limits, and HVAC drafts. A controller
   that only works with generous sim physics is a bug.
5. 3D physics simulation (NVIDIA Isaac Sim on a cloud GPU) is an approved
   investigation track for docking/flight control; the 2D web sim remains the
   product UI.
6. Every check-in, detection, escalation, flight, and config change is logged and
   visible. The audit log is append-only — a flight recorder.

## Article III — Own the entire tech stack

1. Default: **build it ourselves.** Self-hosted open weights we run (Moonshine,
   Pocket TTS/Chatterbox, Piper, MediaPipe, Silero, microWakeWord) count as ours.
   Hosted third-party APIs do not.
2. A third-party component is permitted ONLY if (a) it is significantly better
   than the best we can build/self-host, or (b) we tried and provably can't make
   ours work — and even then it sits behind our own adapter with a written
   replacement path.
3. **Sanctioned exceptions (as of 2026-07-25):**
   - **The frontier LLM brain** — hosted models are significantly better on the
     safety-critical axis (not confidently wrong to a vulnerable person). Hosted
     primary, local 7–8B as a first-class offline fallback. The VOICE is identical
     in both modes, so the user can never tell which brain is driving.
   - **Twilio for demo calls only** — behind the notifier adapter; replacing it
     with our own telephony path is on the roadmap, not optional.
4. Voice pipeline is ours end to end: microWakeWord (wake) + separate distress
   model, Silero VAD, Moonshine STT, smart-turn endpointing, Pocket TTS/Chatterbox
   (Piper = degraded floor). Own the satellite transport protocol (~200 lines) —
   do not build on Wyoming/LVA.
5. Model-agnostic routing stays as internal architecture (vendor hedge + cost
   tiers). It is NOT the customer-facing pitch.

## Article IV — Safety invariants (the bright lines)

1. **No auto-911.** L3 rings configured humans and shows a full-screen alert.
   Autonomous emergency dispatch requires a signed regulatory review to add.
2. **No clinical ranking, ever** (Brady: "it definitely won't rank"). Meemoo
   reports observations ("no movement for 4 minutes in the bedroom"), never
   severity scores, diagnoses, or care recommendations to staff.
3. **No physiological measurement** in v1 (no temperature, no BP) and no
   disease-specific inference. Adding any of these is a constitution amendment +
   regulatory review (temperature = FDA 510(k) territory).
4. **No generative model in the safety path.** The distress-phrase check
   ("help me", "call someone", "emergency") is local keyword/intent matching that
   works with no API key and no internet. Escalation is a deterministic state
   machine. The LLM handles open conversation only, with refusal-and-handoff
   rails for medical questions.
5. **"Help" is its own always-on detector**, tuned for recall (false alarm =
   cheap question; miss = catastrophe), architecturally separate from the wake
   word. The product name must never collide with it.
6. **Negative buoyancy trim** — loss of power means a slow, gentle descent, never
   a ceiling-parked failure.
7. Geofence at doors/windows + auto-land on egress detection (indoors = no FAA;
   one open door changes that).
8. Fall detection is tuned recall-over-precision, persistence-primary. The blimp
   VERIFIES and TALKS; the base-station camera DETECTS.
9. Spatial policy: conversational mode ≈1.5–1.8 m at/just below eye level with a
   vocal announcement before approaching; ambient mode above head height at
   constant radius; never approach from behind; never spin overhead.

## Article V — Memory & privacy

1. **Meemoo remembers people — without biometrics.** Names, preferences, previous
   workouts, conversation context: YES, stored as explicit structured memory +
   conversational context, keyed by schedule/room/self-identification.
   **Face-recognition templates and voiceprints: NEVER** (Illinois BIPA;
   architectural prohibition — a reviewer must be able to inspect the pipeline
   and find no template store).
2. Transcript storage: **default ON**, per-device user toggle (Brady's call).
   Raw audio is never retained after transcription; nothing leaves the base
   station except opt-in event clips.
3. Local-first perception. Pose skeletons and thumbnails, not raw video streams,
   are the working data.
4. Anti-surreptitious by design: audible self-announcement entering rooms,
   visible recording indicator, physical mic-cut mute switch (electrical, not
   software), one-touch privacy pause, per-recipient permission matrix
   (grant the nurse, deny the son — resident's choice).
5. The robot never claims to be alive or to feel; answers "are you real?"
   honestly and identically every time; doesn't lecture someone out of a fiction
   they've chosen. Spoken AI disclosure + periodic reminders + 988 crisis
   protocol ship in v1 (already law in NY/CA).

## Article VI — Compliance posture: prototype freedom, go-live gates

1. **Prototype phase (now):** build fast, test on ourselves and consenting
   household adults, don't block features on legal review. Brady's rule: if a
   rule must bend for a private, not-live prototype, bend it — BUT the
   architecture stays compliance-ready (consent data model, audit log,
   encryption), because retrofit costs 10×.
2. **GO-LIVE GATES — 100% required before any real user, no exceptions:**
   - [ ] Counsel review (real lawyer): FDA ILQ/890.9 posture, disclaimer set,
         IL + CA consent/recording memo (target states: Illinois + California)
   - [ ] AI-companion-law compliance verified (disclosure, reminders, 988,
         published protocol)
   - [ ] Consent flow + roommate/surrogate consent objects live
   - [ ] Marketing claims policy + forbidden-terms lint in CI
   - [ ] Product liability insurance
   - [ ] LiPo → charge-safety review (or LiFePO4); UL/FCC plan for hardware
   - [ ] Dementia/memory-care explicitly out of scope in v1 terms (revisit later
         with LAR-consent design — the evidence says it could help; the blocker
         is consent capacity, not usefulness)
3. Entity: lives under Acuntel for now.

## Article VII — Product model & go-to-market

1. **Hospitals first** (Brady's call — and it is NOT the government-grant
   channel; hospitals are private B2B buyers purchasing on staffing ROI, fall
   liability, and patient experience). Consequence: **hospital-grade is designed
   in from day one**, not retrofitted:
   - No helium cylinder on site — sealed envelope swaps / field-tech service
   - Envelope = single-patient consumable; every hard part smooth, sealed,
     wipeable with EPA-registered disinfectants
   - 60601-1 medical-grade power supply in the base station BOM; 60601-1-2 EMC
     test before hospital pilots
   - Latex-free stated on the spec sheet
   - Pre-assembled facility compliance packet (cleaning IFU, EMC report, helium
     plan)
   State aging agencies remain a later channel option, not a dependency.
2. **Dual-track business model:** (a) **Managed** — customer pays a subscription,
   we run the models, the credits, the helium logistics; this is the default and
   the margin engine. (b) **Self-serve** — technical owners bring their own
   models/keys and run their own plan. Same software.
3. **The preset system is the Setup Studio's core UX:** a role picker
   (Companion · Personal Trainer · Hospital Check-in · Tour Guide · Tutor — all
   kept in v1), each role opening personality sub-presets (e.g. Trainer →
   hardcore / encouraging / keeps-it-simple), each combination shipping a tuned
   base context. Power users can open and edit the raw context; everyone else
   never has to.
4. **Voice options per character:** warm older man ("Morgan-Freeman-like" energy,
   not an imitation), a child voice, a female voice — selectable in the Studio.
   English first; architecture leaves the door open to other languages.
5. Helium logistics is the physical subscription: dock load cell measures trim
   drift; dock-integrated cartridge auto-top-off is the target mechanism.

## Article VIII — Success metrics (what the dashboard must prove)

1. Engagement **trajectory** (user-initiated share over weeks), not vanity totals.
2. Reminder adherence with prompts-required.
3. **False alarms per week as a published headline number.**
4. **Human-contact tracking — the anti-substitution metric:** calls placed,
   visits arranged. Rising Meemoo usage with falling human contact = defined
   product failure.
5. Reliability: hours of unattended operation per human intervention — the metric
   no wheeled or rotored competitor can match.
6. Abandonment early-warning composite (initiation ↓ + session length ↓ +
   missed reminders ↑).

## Article IX — Engineering law

1. Python 3.11+/FastAPI/SQLite backend; React+Vite+Tailwind web; TypeScript
   strict; files under 300 lines; type hints; no bare excepts; structured logging.
2. Guardian state machine + fall detection get real pytest coverage, including
   the "help me" bypass and acknowledgment-halts-escalation. Perception tests run
   on bundled GMDCSA-24/CaucaFall landmark fixtures (committed as JSONL, not
   video).
3. Missing credentials never crash startup; every subsystem degrades gracefully;
   the scripted no-API-key check-in mode always works.
4. `make dev` runs everything on a laptop. Target hardware: dedicated base
   station (Mac mini class — Brady will purchase); dev on MacBook.
5. Every feature must survive the demo script end-to-end before it's "done."
