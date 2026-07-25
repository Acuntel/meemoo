# Step 01 — Core: event bus, database, logging

**Goal:** the nervous system every module plugs into.
**Read first:** CONSTITUTION Art. II, V; MASTER_PROMPT §architecture + §data-model; TODO Phase 1.

## Build

1. **Event bus** (`meemoo/core/bus.py`): async pub/sub. Typed topic strings
   (`person.detected`, `person.down`, `person.recovered`, `utterance.heard`,
   `checkin.due`, `escalation.*`, `flight.*`, `dock.*`). Wildcard subscribe
   (`person.*`), replay-last-event for late subscribers, no module ever imports
   another module's internals — bus only. Full unit tests.
2. **Models** (`meemoo/core/models.py` + alembic migrations) — all keyed by
   `device_id`: devices, persons, contacts (ordered), provider_keys (Fernet-
   encrypted column, never logged), model_config (tier→provider+model),
   checkin_schedule, events (append-only, typed, indexed device+time),
   conversations, messages, alerts, usage, routes, waypoints, settings,
   **consent_records** (person-scoped; subject/scope/method/consenting-party/
   surrogate fields — Art. V), **audit_log** (append-only; DB trigger or guard
   blocks UPDATE/DELETE), **memory_facts** (per-person structured memory:
   names, preferences, workout history; NO biometric columns — by design,
   documented in the model docstring).
3. **Logging** (`meemoo/core/logging.py`): structlog-style JSON + pretty console;
   helper that stamps model/prompt/threshold versions onto escalation-relevant
   records.
4. **Crypto** (`meemoo/core/secrets.py`): Fernet key from env or generated to
   local file; encrypt/decrypt provider keys; test proves keys never appear in
   logs or repr.

## Gate
- Bus tests: pub/sub, wildcard, replay, unsubscribe, concurrent publishers.
- Migration creates the full schema; audit_log rejects UPDATE/DELETE in a test.
- `make check` green.
