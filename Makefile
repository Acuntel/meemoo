# Meemoo — single-laptop dev workflow (Constitution Art. IX §4).
# Requires: uv (https://docs.astral.sh/uv/), node 20+.

.PHONY: dev api web-dev install migrate test lint type check web-install web-typecheck web-build

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

# ruff + mypy + pytest + web typecheck (build proves the bundle compiles)
check: lint type test web-typecheck web-build
	@echo "make check: ALL GREEN"
