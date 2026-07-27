# Meemoo — single-laptop dev workflow (Constitution Art. IX §4).
# Requires: uv (https://docs.astral.sh/uv/), node 20+.
# Firmware targets need PlatformIO (`pio`); override with PIO=/path/to/pio.

PIO ?= pio
PIO_HINT = PlatformIO is not installed. Fix: python3 -m venv ~/.pio && ~/.pio/bin/pip install platformio, then rerun with PIO=~/.pio/bin/pio (or add it to PATH). See firmware/README.md.

.PHONY: dev api web-dev install migrate test lint type check web-install web-typecheck web-build demo-voice demo-brain demo-guardian demo-flight flash-bench flash-flight firmware-check

# ------------------------------------------------------------------ install
install:
	uv sync
	cd web && npm install

# ---------------------------------------------------------------------- dev
# One command: FastAPI (reload) + Vite dev server in parallel.
dev:
	$(MAKE) -j2 api web-dev

api:
	uv run uvicorn meemoo.api.app:app --reload --host 127.0.0.1 --port 8000

web-dev:
	cd web && npm run dev

# ------------------------------------------------------------------ migrate
# Programmatic Alembic runner (stock CLI needs migrations/env.py, which the
# .env file-protection hook blocks — see meemoo/core/migrate.py).
migrate:
	uv run python -m meemoo.core.migrate

# --------------------------------------------------------------------- demo
# Step-03 gate: talk to the laptop, hear Meemoo in each of the three voices.
# Live mic/speaker needs `uv sync --group voice`; degrades to typed input.
demo-voice:
	uv run python -m meemoo.voice.demo --voices-check
	uv run python -m meemoo.voice.demo

# Step-04 gate: same check-in conversation across providers by config flip.
demo-brain:
	uv run python -m meemoo.brain.demo --provider fake
	uv run python -m meemoo.brain.demo --provider scripted
	uv run python -m meemoo.brain.demo --compare-presets

# Step-05 gate: simulated fall → verify → L1 → ack (then the no-ack L3 ladder).
demo-guardian:
	uv run python -m meemoo.guardian.demo
	uv run python -m meemoo.guardian.demo --no-ack

# Step-06 manual gate: watch the whale fly a round, dock, charge, depart
# (ASCII debug view; drop --fast for real-time pacing).
demo-flight:
	uv run python -m meemoo.flight.demo --fast

# ----------------------------------------------------------------- firmware
# Stage 3 (docs/BUY_AND_BUILD.md): flash the bench target, watch the serial
# numbers while the decibel app listens at 1 m.
flash-bench:
	@command -v $(PIO) >/dev/null 2>&1 || { echo "$(PIO_HINT)"; exit 1; }
	cd firmware && $(PIO) run -e bench -t upload && $(PIO) device monitor -b 115200

# Stage 6: flash the flight target (copy firmware/include/meemoo_config.sample.h
# to meemoo_config.h with your WiFi first).
flash-flight:
	@command -v $(PIO) >/dev/null 2>&1 || { echo "$(PIO_HINT)"; exit 1; }
	cd firmware && $(PIO) run -e flight -t upload && $(PIO) device monitor -b 115200

# Compile both firmware targets when pio exists; skip honestly when it
# doesn't (a missing toolchain must never break CI).
firmware-check:
	@if command -v $(PIO) >/dev/null 2>&1; then \
		cd firmware && $(PIO) run -e bench -e flight; \
	else \
		echo "firmware-check: skipped ($(PIO) not on PATH - see firmware/README.md)"; \
	fi

# --------------------------------------------------------------------- test
test:
	uv run pytest

lint:
	uv run ruff check meemoo tests

type:
	uv run mypy

web-typecheck:
	cd web && npm run typecheck

web-build:
	cd web && npm run build

# ruff + mypy + pytest + web typecheck + firmware compile (when pio present)
check: lint type test web-typecheck web-build firmware-check
	@echo "make check: ALL GREEN"
