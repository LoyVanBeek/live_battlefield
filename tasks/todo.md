# Fix: missing `psycopg` on deployed system (Alembic migration crash)

## Root cause
- `migrations/env.py` built the sync URL as bare `postgresql://...` (stripped `+asyncpg`).
- Dockerfile installed from `pyproject.toml`, not `uv.lock` → rebuild resolved `sqlalchemy[asyncio]>=2.0.0` to SQLAlchemy 2.1.
- SQLAlchemy 2.1 changed the default driver for bare `postgresql://` from psycopg2 → psycopg 3; `psycopg` is not shipped → `ModuleNotFoundError`.

## Plan (approved: A + D)
1. **A** `app/config.py`: `database_url_sync` replaces `+asyncpg` → `+psycopg2` (explicit shipped driver).
2. `migrations/env.py`: drop redundant second `.replace("+asyncpg", "")`.
3. **D** `Dockerfile`: install from `uv.lock` so rebuilds are reproducible.

## Tasks
- [x] `app/config.py`: one-line fix (`+psycopg2`)
- [x] `migrations/env.py`: cleanup
- [x] `Dockerfile`: lockfile-based install
- [x] Verify: sync URL prints `postgresql+psycopg2://...`
- [x] Verify: `uv run pytest tests/` → 191 passed; ty check skipped (string-only change, no type surface)
- [x] Verify: `docker compose build app` → image has SQLAlchemy 2.0.47 + psycopg2 2.9.11 (locked)
- [x] Verify: `docker compose up -d` → migrations applied, DB at `008`, HTTP 200, healthcheck green

## Second issue found & resolved (user decision)
- The deployed DB was stamped at revision `015` from the unmerged `feature/specials` branch
  (its events included `TSUNAMI` / `SPECIAL_AMMO_GRANTED`, which main's `EventType` can't parse —
  a plain `stamp 008` would have 500'd the event feed).
- User chose **reset**: `docker compose down` + `docker volume rm live_battlefield_postgres_data`
  (pgadmin config volume kept), then `up -d` on main. Fresh DB migrated 001→008 cleanly.

## Implementation note
- First attempt used `uv sync --frozen --no-install-project --system` — invalid: `uv sync` has no
  `--system` flag (build caught it). Final form: `uv export --frozen --no-dev --no-emit-project` →
  `uv pip install --system -r`, which keeps the system-site-packages layout the app, healthcheck,
  and `Dockerfile.e2e` already rely on.

## Follow-ups
- When `feature/specials` merges, the fix rides along via main; no action needed.
- A remote deployed host needs these commits pulled + image rebuilt; if its DB is also
  specials-stamped, reset or reconcile it the same way.
