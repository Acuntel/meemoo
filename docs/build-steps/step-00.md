# Step 00 — Project scaffold

**Goal:** a runnable skeleton: Python package, web app shell, `make dev`, CI.
**Read first:** docs/CONSTITUTION.md Art. IX; docs/MASTER_PROMPT.md §tech-stack + §architecture.

## Build

1. `pyproject.toml` — package `meemoo`, Python 3.11+, deps: fastapi, uvicorn,
   sqlalchemy, alembic, apscheduler, pydantic-settings, cryptography, websockets,
   pytest, pytest-asyncio, ruff, mypy. Vision/voice deps (opencv-python,
   mediapipe, faster-whisper etc.) enter in their own steps — keep the scaffold
   fast to install.
2. Package dirs per the spec's module map: `meemoo/{core,perception,voice,brain,guardian,flight,fleet,api}/__init__.py`
   plus `web/` (Vite + React + TS strict + Tailwind).
3. `meemoo/core/config.py` — pydantic-settings loader; EVERY optional credential
   defaults to None and never crashes startup. `.env.example` documenting every
   variable (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, OLLAMA_URL,
   TWILIO_* (demo only), MEEMOO_DB_PATH, VIDEO_SOURCE, etc.).
4. `Makefile`: `make dev` (uvicorn + vite dev, single command), `make test`,
   `make check` (ruff + mypy + pytest + web typecheck).
5. Minimal FastAPI app serving `/api/v1/health` + the built web bundle; minimal
   React page saying "Meemoo" with Tailwind working.
6. CI workflow (.github/workflows/ci.yml): ruff, mypy, pytest, web
   typecheck+build. ⚠️ Acuntel org Actions billing was BLOCKED 07-21 — if runs
   don't start, note it and rely on local `make check` (precedent: KARL).
7. Formal name screen (Phase 0 leftover): run a USPTO TESS search for "Meemoo"
   (robotics/health/software classes) via web search; record findings in
   docs/TODO.md. Domains are Brady's task — remind him if unregistered.

## Gate
- `make dev` starts clean on a fresh clone; browser shows the shell page.
- `make check` passes.
- `pytest` runs (even if only a config smoke test exists).
