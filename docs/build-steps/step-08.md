# Step 08 — Integration: the demo script end-to-end

**Goal:** the exact six-step demo from MASTER_PROMPT §demo-script passes cold,
and degradation never crashes.
**Read first:** MASTER_PROMPT §demo-script + §quality-bar; CONSTITUTION Art. IX.

## Build / verify

1. Fresh-clone run: `git clone && make dev` on a clean checkout → demo steps
   1–6 in order:
   1. Studio config "Ruth" → extract → save → key or skip
   2. Dashboard: whale docked, floor plan, next check-in scheduled
   3. "Run round now" → drift → real voice check-in with medication reminder →
      return → timeline entry with mood summary
   4. Lie on floor (or fall clip via file source) → person.down → whale flies
      over in sim → "are you okay?" ×2 real audio → CONCERN → L1 → simulated
      call screen (or real Twilio ring) → Acknowledge → halt → audit trail
   5. "Help me" spoken mid-conversation → immediate escalation, no LLM in path
   6. Studio: switch conversation tier provider → next check-in uses it →
      cost meter reflects it
2. Degradation matrix (automated where possible): no API key / no camera / no
   mic / sim stopped / no Twilio / no network — every combination keeps the app
   alive and the scripted safety loop functional.
3. README rewrite: 5-minute quickstart, architecture diagram (mermaid), the
   MQTT hardware handoff spec, fake-vs-real table, and the /build-step system
   documented for future sessions.
4. Fix everything that broke; re-run until clean. Record a short screen capture
   of the full demo for Brady if tooling allows.

## Gate
- All six demo steps pass consecutively on one cold start, witnessed by logs.
- Degradation matrix green. `make check` green. README accurate.
