# Step 07 — API + Web: Setup Studio, Family Dashboard, Live View, Sim

**Goal:** the complete product surface.
**Read first:** MASTER_PROMPT §fleet/studio, §dashboard, §api; CONSTITUTION
Art. VII.2–4 (dual-track model, presets, voices), VIII (every success metric
becomes a dashboard element), V.4 (privacy surfaces); research/07 §F (the 15
research-credibility features — items 1–15 map to concrete panels here).

## Build

1. REST CRUD `/api/v1/...` for devices, persons, contacts, presets, keys
   (write-only, masked read), schedules, routes, alerts (+ acknowledge),
   conversations, events, usage, consent records. OpenAPI docs must render.
2. WebSockets: `/ws/video` (annotated frames), `/ws/sim` (position/battery/
   dock state), `/ws/events` (live event stream), `/ws/voice` (browser PTT
   audio both directions).
3. **Setup Studio** (chat-style, modern AI-chat feel):
   - Conversational config: owner types plain language ("You're checking on my
     mom Ruth…") → brain extracts structured config → review/edit screen →
     save; raw instructions stored as custom context.
   - Preset role picker (5 roles) → personality sub-presets → voice selection
     with audio preview (3 characters) — the Art. VII.3 flow.
   - Managed-vs-self-serve framing: managed is the default face; BYO
     provider/key management under "Advanced". Live estimated monthly cost.
   - Privacy panel: transcript toggle (default ON), per-recipient permission
     matrix, privacy pause, consent record view.
4. **Family Dashboard** (warm, calm — worried-daughter-at-11pm bar; soft
   colors, rounded, generous whitespace, zero jargon):
   - Today: check-in timeline with mood notes.
   - Live View: sim position + battery + dock + annotated camera feed.
   - Alerts: active/history with evidence + Acknowledge.
   - History: rounds, conversations (if stored), detections, cost meter.
   - **Research-credibility layer**: engagement trajectory (user-initiated
     share over time, week-6 marker), adherence w/ prompts-required,
     false-alarms/week headline, human-contact tracking, abandonment
     early-warning composite, CSV export, synthetic-data demo mode (labeled).
5. Simulated incoming-call full-screen takeover for the no-Twilio escalation
   demo; whale sprite in the sim view drifts with floaty easing (never
   robotic straight lines).
6. Run the ui-reviewer pass on every screen; fix what it flags (Brady's
   layout-smoke rule applies before any deploy).

## Gate
- Demo-script steps 1–2 pass fully: Studio → "Ruth" extraction → review →
  save → key paste (or skip) → dashboard shows whale on dock + next check-in.
- All four WebSockets stream live data; OpenAPI page renders; `make check` +
  web typecheck green.
