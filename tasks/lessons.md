# Lessons Learned

## Mocking `from X import Y` imports
- `patch.object(module, "func")` patches the attribute on the module object, but does NOT affect names imported via `from module import func` — those are direct references to the original function
- Use `patch("importing_module.func")` instead (the dotted path of where the name is used, not where it's defined)
- Example: `from app.models import get_all_events` in `app/api/routes.py` → use `patch("app.api.routes.get_all_events")`, not `patch.object(models, "get_all_events")`

## AsyncMock as dependency override
- `lambda: AsyncMock()` for `Depends(get_api_db)` is dangerous: `AsyncMock().execute()` returns a coroutine, so `result.scalars().all()` fails with `AttributeError: 'coroutine' object has no attribute 'all'`
- The conftest-level mock of `create_async_engine` handles async DB mocking more cleanly — prefer that approach
- Don't mix `dependency_overrides` with `AsyncMock` when the conftest already provides engine-level mocking

## pydantic-settings and `.env` extra fields
- `SettingsConfigDict(env_file=".env")` defaults to `extra="forbid"`, which rejects env vars not declared as model fields
- When `.env` contains vars used by other services (e.g., `NGROK_AUTHTOKEN` for docker-compose), add `extra="ignore"` to the config

## pytest-asyncio installation
- If `pytest-asyncio` is in `[project.optional-dependencies] dev`, it won't be auto-installed with the base dependencies
- Async test failures ("async def functions are not natively supported") usually mean `pytest-asyncio` is missing
- Install with: `uv sync --extra dev`

## Persisting side-effect DB records when adding domain events
- When adding a `TeamJoinedEvent`, the token must ALSO be persisted to the `team_tokens` table via `create_team_token()`
- The `TeamJoinedEvent` payload stores the token for game-state replay; the `team_tokens` table is used for auth lookups
- Both MUST be written together — this is a classic "write model" vs "read model" pattern where the same data serves two purposes
- Call `create_team_token()` immediately after `save_event()` for the `TeamJoinedEvent`

## AI player storage is now game-scoped
- `_ai_players` is `dict[str, dict[str, AIPlayer]]` keyed by `game_id` then `color`
- All AI functions (`get_ai_player`, `add_ai_player`, `remove_ai_player`, `get_all_ai_players`, `is_all_ai_paused`) take `game_id` as first arg
- Bot handlers must pass `player.game_id` to these calls — old single-arg signatures silently search under `""`/`None`

## Color availability checks must be game-scoped
- Since `(game_id, color)` unique constraint replaced global unique `color`, all "is this color taken?" checks must filter by `game_id`
- `get_all_players()` returns ALL players across ALL games — always filter with `p.game_id == current_game_id`
- `get_all_teams_in_game()` only checks `Role.TEAM` players, missing AI players — use `get_all_players_in_game()` for full collision detection

## Stray `...` in JS template breaks entire script
- A bare `...` (ellipsis placeholder) anywhere in a `<script>` block causes `SyntaxError: Unexpected token` and prevents ALL code in that block from executing
- Even though `loadTeams` and `apiCall` appear before the error in the source, the entire block fails to parse — nothing runs
- After template changes, verify with `node --check` that the extracted JS is valid
- Docker images must be rebuilt (`docker compose build`) for template changes to reach the container — `docker compose restart` alone only restarts the process with the image-baked code

## E2E and prod compose share the project name — never `down --remove-orphans`
- `docker-compose.yml` and `docker-compose.e2e.yml` are both project `live_battlefield` (derived from the directory name), so containers/networks interleave
- `docker compose -f docker-compose.e2e.yml down --remove-orphans` will treat the PROD stack (`app`, `ngrok`, `pgadmin`, `postgres`) as orphans and delete those containers
- Only ever tear down the test stack by exact service names: `docker compose -f docker-compose.e2e.yml down test-app test-postgres`
- Containers are replayable from config; data lives in named volumes — never pass `-v` unless you truly want the DB gone

## Stale E2E POM vs redesigned GM UI
- `gm_page.py` `join_color_select` targets `#join-color`, which no longer exists (replaced by click-to-join per-color inputs). 7 E2E tests (`test_full_flow`, most of `test_gm_page`) fail on this pre-existing debt — reproduce on baseline, do not attribute to new changes

## Piped commands mask exit codes in `&&` chains
- `uv run pytest ... | tail -2 && git commit ...` commits on test failure — the chain sees `tail`'s exit status (0), not pytest's
- Bit me once: committed a failing test and had to amend (commit `5128d4b` era, quiz scoping test)
- Rule: run pytest as its own command and check the result before composing; when piping is unavoidable, use `set -o pipefail` or capture output to a file and echo the real exit status
- Same applies to audit/lint tools whose summary lines hide a non-zero exit

## piped audit output truncation hides remaining findings
- `pip-audit | tail -N` showed only the last findings — fixing one package revealed the next (pillow → idna → mako → click needed FOUR rounds)
- Rule: write audit output to a file and inspect it fully; trust the exit code, not the visible tail

## Naive TCP relay needs `TCP_NODELAY` — Nagle stalls cost ~43ms per request
- The E2E loopback relay (conftest, gives browsers a trustworthy `http://localhost` origin for Geolocation) initially forwarded bytes with Nagle on: every API round trip went 4ms → 47ms (delayed-ACK signature)
- That 40ms hit three tests asserting *immediately* after `page.goto` on JS-fetch-populated content (`test_join_page_loads`, `test_full_color_block`, `test_navigate_to_events_from_gm`) — deterministic failures, but the root cause was proxy latency, not the tests
- Rule: set `TCP_NODELAY` on BOTH ends of any forwarding socket (accepted + upstream); when a relay/proxy changes timing, measure before rewriting callers — `performance.getEntriesByType('resource')` per fetch makes it a number, not a guess
- Chromium's `--unsafely-treat-insecure-origin-as-secure` flag is dead in Chrome 153 (`isSecureContext` stays false) — don't reach for it to fake a secure context; loopback is trustworthy with no flags

## Green `ty check app` ≠ green CI — run the exact CI command
- AGENTS.md told me to run `uv run ty check app`; CI and the pre-commit `ty-check` hook run `uv run ty check` (repo-wide)
- Result: 4 consecutive red CI runs (161–164) on `Run type checks` while every local check I ran reported clean — the two `ty` errors lived in `tests/` and `tests_e2e/`, outside the `app` path
- Worse: CI's `Run tests` and `Audit dependencies` steps sit *behind* the type check, so a type error silently hid a real `pip-audit` failure (anyio 4.12.1) for four runs
- Rule: before calling anything done, run the commands from `.github/workflows/ci.yml` verbatim, in the same order, and confirm which downstream steps were blocked by an earlier failure
- `# type: ignore[attr-defined]` is mypy syntax — ty does not honour it; use `# ty: ignore[<ty-rule>]` or a `cast()` that keeps the attribute actually checked
- AGENTS.md now documents `uv run ty check` (repo-wide) plus the full CI sequence
