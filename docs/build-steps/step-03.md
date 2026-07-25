# Step 03 — Voice: the ears and mouth (own-stack)

**Goal:** full local loop: mic → STT → (brain placeholder) → TTS → speaker, with
the distress bypass that works offline.
**Read first:** docs/research/02-voice-stack.md §A (model picks + latency
budget), §C (wake word), §D (barge-in layers); CONSTITUTION Art. III.4, IV.4–5,
V.2, V.5. Reusable Brady code: `~/Desktop/restoration-one/whisper-service/main.py`
(faster-whisper FastAPI pattern) and the anti-hallucination lessons in memory
`project_ptt_dictation` (VAD, repetition collapse, vocab prompts).

## Build

1. Audio I/O abstraction: server mic/speaker now; design the framed satellite
   transport (~200 lines, own protocol — NOT Wyoming) as the later swap point.
2. `STT` interface → primary impl **Moonshine v2 Streaming** (fallback impl:
   faster-whisper small — port the restoration-one service pattern). Whisper's
   silence-hallucination is why Moonshine is primary (elderly pauses).
3. `TTS` interface → primary impl **Pocket TTS** (or Chatterbox if Pocket
   integration fights back; do an hour of side-by-side listening and note the
   choice); **Piper** as the always-works offline floor. Three voice characters
   configured per device: warm older man / child / female — pick and commit
   actual voice models/embeddings for each.
4. Silero VAD + smart-turn endpointing; sessions open on PTT (wake word behind
   an interface — openWakeWord impl optional this step), hold rolling context,
   close after 45 s silence.
5. **THE DISTRESS BYPASS (most important item):** local phrase/intent detector
   for "help me / I need help / call someone / emergency" + fuzzy variants,
   running on EVERY final transcript, publishing `escalation.distress` directly
   — no LLM, no network. pytest proves it fires with all API keys absent and
   network mocked dead.
6. Transcript storage default ON with per-device toggle; raw audio deleted
   post-transcription; conversation + messages persisted via core models.
7. Spoken AI disclosure line at session start + periodic re-disclosure timer +
   988 crisis-protocol path (deterministic templates, logged) — Art. V.5.
8. Barge-in scaffolding only: ducking hooks + "stop" phrase handled from the
   always-on distress/stop detector; full AEC is hardware-phase work.

## Gate
- `make demo-voice`: talk to the laptop, hear a templated reply in each of the
  three voices; measured time-to-first-audio logged (target <2 s on MacBook).
- Distress test green offline. Disclosure lines audible and logged.
