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

## Auto-place died on "dead-end boards" — redraw instead of giving up
- Symptom: intermittent full-suite E2E failures, but a *different* test each time (`test_complete_game`,
  `test_quiz_mode`) — Playwright clicked `#btn-start` for 30s while it stayed `disabled`
- The app explained it once I read the UI instead of guessing: `#start-reason` said "Not all teams have
  placed all ships (1/2)" and `/api/quick/place_all_ships` returned HTTP 200
  `{"success": false, "message": "Could not find placement for patrol_boat"}` — the tests ignore response bodies
- Root cause: `place_all_ships_game_scoped` ran one greedy draw (5000 random tries per ship). Under the
  no-touching rule an early ship can leave *no legal cell* for a later one — measured 3.5% of draws die
  that way — and the code gave up instead of redrawing the board
- Ruling out my own relay: reproduce with a loop that alternates relayed vs direct origin. It failed on
  both → not the relay, one command instead of an argument
- Fix: redraw the whole board on a dead end (`MAX_BOARD_DRAWS = 20`) → 0/1500 failures, mean 0.75ms
- Why tests missed it: auto-place response bodies are never asserted, and the GM Start precondition only
  fails intermittently, surfacing as a click timeout in whichever full-flow test ran the auto-place

## `write` silently overwrites — check the path exists first (self-caught)
- I "created" `tests/test_ship_placement.py` without checking: it already existed (5 geometry tests from
  "Split up tests") → suite went 219 → 218 instead of 219 → 223
- The wrong-direction total was the tell. Know the expected count *before* running the suite
- Rule: `ls`/`git status` a populated directory before writing a "new" file there, and name test files
  after the module they cover (`test_ship_placement_service.py` for `app/services/ship_placement.py`)

## Flicker = destructive `innerHTML` churn, not page reloads — prove the test goes red first
- "The quiz page flickers, I think due to page reloads": the team page never reloads; every SSE state
  push ran `renderActions()` → `actionsEl.innerHTML = html`, destroying and re-creating `#quiz-content`
  with a "loading…" placeholder followed by an async `updateQuizSection()` repaint. Boards were already
  incremental (`renderGrid` caches DOM in `boardGridCache`); `#actions` was the only destructive render.
- Fix pattern: shape-key guard (`gameStatus|quizEnabled|isPaused`) — rebuild only when the panel's shape
  changes, otherwise refresh the few live sub-parts; each sub-render (`updateQuizSection`,
  `renderTargetTeams`) gets its own content signature and writes nothing when unchanged. Side effects of
  the same bug: typed bomb coordinate and chosen `#target-team` were wiped by every opponent move.
- DOM-identity regression test: tag a live element (`dataset.probe`), install a `MutationObserver`
  counting child mutations, trigger a state push via the API (opponent bomb → broadcast), assert the
  tagged element survived and mutations == 0. Existing waits for "a button exists" can't see churn.
- Rule: registered a regression E2E and verified it FAILS against the old template
  (`quiz text is now: 'ParisLondon'`) before shipping — a test that only passes both ways guards nothing.
- Doc drift noticed, not fixed: AGENTS.md's `--video=on-fail` is rejected by the e2e container's
  pytest-browser (`invalid choice`, picks are on/off/retain-on-failure); compose already uses `--video=on`.

## Routed `await` on a patched model → patch with `AsyncMock`, not `MagicMock`
- A route that does `await save_quiz_questions(...)` (model imported inside the function)
  breaks under `patch("app.models.save_quiz_questions")`: a MagicMock is not awaitable →
  `client.post(...)` raises before returning → the test "fails" at the request, not at an assert
- Fix: `patch(..., new_callable=AsyncMock)`; set `mock.return_value` to a real list because
  the route calls `len(result)` (a bare AsyncMock has no `__len__`) — then
  `mock.assert_awaited_once()` matches the awaited call

## `git checkout <ref> -- <file>` stages; `git restore <file>` restores from the INDEX
- "Prove-the-e2e-is-red" flow: `git checkout 63f262a -- app/templates/game_settings.html`
  updates AND stages the old file. After the red run, `git restore <file>` pulled the *old*
  content back (from the index), re-staging the broken template — only a
  `git checkout HEAD -- <file>` (or `git restore --source=HEAD --staged --worktree <file>`)
  recovers. `git status --short` shows a staged `M` when this state bites

## The e2e "54 passed, 54 errors" pattern is a permissions teardown noise, not failures
- The compose ships `--video=on` with `./test-results:/app/test-results` and the container
  as UID 1000. Docker creates a *fresh* mount root-owned, so Playwright's teardown
  `video.save_as()` raises `PermissionError` for EVERY test (PASS + teardown ERROR, exit 1).
  That is why CI marks the e2e job `continue-on-error`.
- One-off debug runs leave root-owned `test-results/` on the host behind (rm-as-yourself
  works; chown doesn't). To see a REAL clean signal locally run
  `docker compose ... run --rm --user root test-e2e` → spotless 54/54.
- Don't "fix" by editing the compose for a private run; document instead.
