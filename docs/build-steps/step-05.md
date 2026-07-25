# Step 05 — Guardian: the safety spine (most tests in the codebase)

**Goal:** the escalation state machine, check-in scheduler, contacts, and
notifier — deterministic end to end.
**Read first:** MASTER_PROMPT §guardian (state machine is EXACTLY this);
CONSTITUTION Art. IV (all), VIII.3 (false-alarm budget); research/03 §C.2
(audit-log requirements — the liability record).

## Build

1. The state machine as a pure, side-effect-free module (effects injected):
   IDLE → CHECK_IN_DUE → CHECKING → OK/NO_RESPONSE → CONCERN → verify (fly to
   person in sim + "are you okay?" ×2) → OK | ESCALATE_L1 → (N min, no ack) →
   ESCALATE_L2 → ESCALATE_L3. `person.down` enters CONCERN from ANY state.
   `escalation.distress` (the voice bypass) enters ESCALATE_L1 directly.
2. L3 = ring the configured TEST number + full-screen alert. Real-911 flag
   exists, ships OFF, documented TODO with the regulatory gate note.
3. Contacts CRUD (ordered, relationship, phone, prefs). Acknowledgment from
   dashboard (and Twilio SMS reply when creds exist) halts escalation and logs
   who/when/latency.
4. Check-in scheduler (APScheduler, per-device times, default 9a/1p/6p/9p):
   fires `checkin.due` → flight round (sim) + real voice check-in.
5. Notifier adapter interface: `TwilioNotifier` (demo-only per Art. III.3 —
   reuse patterns from Brady's Paradise call bot) + `SimulatedNotifier` (drives
   the fake incoming-call screen). Own-telephony replacement documented.
6. Every transition = immutable audit row: timestamp, trigger, evidence link
   (thumbnail/transcript ids), model/threshold versions. False-alarms-per-week
   counter computed and exposed.

## Gate (the deepest test suite)
- pytest: full state walk; CONCERN verify path both outcomes; "help me" bypass
  straight to L1; ack halts at L1 and L2; timeout ladders L1→L2→L3; person.down
  from every state; scheduler fires; audit rows immutable + complete; zero-creds
  path uses SimulatedNotifier without error.
- End-to-end sim: fake `person.down` → whale flies over (sim) → two voice asks
  (real audio) → no response → L1 → dashboard-less ack via API → halted.
