# Step 04 — Brain: model-agnostic intelligence + presets

**Goal:** the conversation engine with tiered routing, presets, memory, and a
scripted fallback that keeps the safety loop third-party-free.
**Read first:** MASTER_PROMPT §brain; CONSTITUTION Art. III (LLM exception
terms), IV.2/IV.4 (never ranks, no safety-path LLM), V.1 (memory w/o
biometrics), VII.3–4 (presets + voices); research/07 §F items 5–6 (anti-
repetition + continuity — implement these).

## Build

1. Provider adapter interface `complete(messages, model, max_tokens) -> response`
   (+ streaming variant). Four adapters, one file each: Anthropic, OpenAI,
   Google, Ollama. A fifth provider must require exactly one new file — prove it
   with a `FakeProvider` test adapter.
2. Tier router: `tier.reflex` / `tier.conversation` / `tier.reasoning` mapped
   per-device in model_config; task-type → tier selection; per-request + daily
   usage rows → cost meter. NOTE Art. IV: the reasoning tier may ADVISE on
   ambiguous non-safety judgments, but escalation decisions remain guardian's
   deterministic state machine — the LLM never gates an escalation.
3. Personality assembly: base template (warm, short spoken-length replies for
   TTS) + **preset system**: role picker (Companion / Personal Trainer /
   Hospital Check-in / Tour Guide / Tutor) × personality sub-presets (e.g.
   Trainer: hardcore / encouraging / keeps-it-simple) as versioned YAML in
   `meemoo/brain/presets/`; + owner custom context (raw-editable); + device
   context (person's name, reminders, mode, memory facts).
4. Memory: post-conversation extraction into memory_facts (names, preferences,
   workouts — explicit, inspectable, deletable; NO biometrics). Mood-note
   summary per conversation for the dashboard timeline.
5. Anti-repetition paraphrase bank per intent (10+ variants for greetings,
   praise, reminders), sampled without replacement in a window, repetition-rate
   metric logged. Continuity behaviors: name at greet/farewell, reference last
   session, forward-reference next.
6. Scripted no-API-key fallback: templated check-in dialogue tree — the demo
   must fully work with zero keys.
7. Medical-question refusal-and-handoff rail (deterministic detector + template).

## Gate
- Same check-in conversation runs on Anthropic, on Ollama, and on scripted
  fallback purely by config flip; transcripts show the same voice/persona.
- Cost meter accumulates; preset switch (nice-trainer → hardcore-trainer)
  visibly changes tone; repetition rate reported.
