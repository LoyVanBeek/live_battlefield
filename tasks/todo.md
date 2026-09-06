# Sunk-ship line + hit/miss toast colors

## Plan (approved)
1. When a ship is fully sunk, draw a diagonal slash across it (team page + GM page web UI; PNG boards unchanged).
2. Bomb miss → red toast; hit → green toast (current behavior). Error guards stay red.

## Tasks
- [ ] Backend: add `result["hit"]` to `/api/execute` bomb response (routes.py)
- [ ] team.html: toast call sites use `result.hit` for color (lines ~1245, ~1262)
- [ ] team.html: sunk-ship diagonal line — `.board-grid` position:relative, `.sunk-line` CSS, `drawSunkShipLines(grid)` helper hooked into `renderGrid` (includeShips only)
- [ ] game_master.html: same sunk-line for `.team-board-cell` grids via `updateBoardFromData`
- [ ] Verify: `uv run ty check app`, `uv run pytest tests/`, E2E (docker compose test stack: test_team_page.py, test_complete_game.py)
- [ ] Commits: step-by-step (backend+toast, team.html line, game_master.html line)

## Design notes
- Ships are contiguous cell runs; no-touching rule (ships.py:59, Chebyshev distance ≤1 rejected) guarantees one run = one ship.
- Run grouping: horizontal runs first, then vertical runs on unused cells, then singles.
- Overlay: absolutely positioned rotated div, corner-to-corner (`atan2(h,w)`), length = diagonal + overshoot, `pointer-events:none`, darkred `rgba(139,0,0,0.85)` (matches board.py's darkred sunk color).
- Grids are cached (`boardGridCache`) → remove-then-redraw overlays each pass for idempotency.
- `result["hit"]` is additive; `success` semantics unchanged so no other consumer breaks.

## Review
- All 3 feature commits done (backend+toast, team.html line, GM line).
- `uv run ty check app`: pass. `uv run pytest tests/`: 134 passed.
- E2E stack actually lives in `docker-compose.e2e.yml` (AGENTS.md quick-start was missing the `-f` flag — fixed).
- Full E2E run with these changes: 25 passed, 7 failed — bisected by injecting pre-change templates/routes into the running test-app: failures reproduce identically on old code (`#join-color` empty on GM page) → pre-existing on branch, unrelated.
- Functional verification (targeted Playwright probe, 9/9 checks):
  - API: bomb response `hit=false` on miss, `hit=true` on hit.
  - Team page UI: miss → `#toast.error` red; hit → `#toast.success` green (real click path).
  - Sunk battleship (4 cells): victim's team page shows 4 `.board-cell.sunk` + exactly one `.sunk-line`, centered on the run, rotated 14.04° = atan2(30,120) for a 4-cell horizontal ship.
  - GM page: 1 `.sunk-line` on blue's board, 4 sunk cells.
- E2E subset re-run after verification: test_team_page, test_complete_game, test_ship_editor, test_trickle — 6 passed.
- Test stack torn down (`docker compose -f docker-compose.e2e.yml down -v`).

---

# v2: straight strikethrough + public sunk ships

## Plan (approved)
1. Straight strikethrough along ship axis (horizontal bar for horizontal ships, vertical for vertical; singles horizontal) — team.html + game_master.html.
2. Sunk ships public to all viewers: public grid exposes p/k for sunk-ship cells only; attacker sees line on victim's public board. Live ships stay hidden.

## Tasks
- [ ] Commit 1: straight line geometry (no rotation) in both templates
- [ ] Commit 2: team_view.py public sunk reveal + renderGrid paint/gate + unit test
- [ ] Verify: ty, pytest, Playwright probe (2 orientations, attacker view), E2E subset
- [ ] Deploy: build app image, restart
- [ ] Review section

## Review (v2)
- Commits: `bfe255a` straight strikethrough (both templates), `d43925b` public sunk-ship reveal (team_view.py + renderGrid + tests/test_team_view.py).
- `uv run ty check app`: pass. `uv run pytest tests/`: 137 passed (3 new).
- Playwright probe: 13/13 — attacker sees sunk ships + straight bars (126x4 horizontal, 4x96 vertical) on victim's public board; live ships hidden (7/31 cells revealed); victim private board unchanged; own board line-free; toasts still red/green.
- E2E subset (team page, complete game, ship editor, trickle): 6 passed.
- Deployed: `docker compose build app && up -d app`; container serves new code (verified).
- Probe assertion fix: 10 ships = 31 cells, not 10 (initial 12/13 was a test bug, not code).

## v3: inset strikethrough
- Commit `b0615bf`: line length = run length − 12px (6px inset per end) in both templates.
- Probe re-run on rebuilt test-app: 13/13 (108px horizontal bar in 4-cell run, 78px vertical bar in 3-cell run, still centered).
- Note: first probe run hit stale test-app image (forgot --build) — rebuilt and re-verified.
- Deployed: dev image rebuilt, app restarted, new code confirmed in container.

---

# v4: translate bomb-flow toasts (hit/miss/sunk + error guards)

## Plan (approved — scope "Both": result toasts AND guard toasts)
1. Backend (`routes.py`): add structured fields to bomb success (`hit`, `sunk`, `ship_type`, `target_name`, `coord`, `bombs_left`, optional `winner`) and `error_key` to guard returns (game_not_started, game_paused, team_doesnt_exist, target_doesnt_exist, no_bombs, invalid_coord, target_destroyed, already_bombed). Keep `result["message"]` for backward compat (Telegram bot, other consumers). `_check_game_paused` gains `error_key` + `minutes`.
2. Frontend (`team.html`): `bombToastText(r)` helper composes message via `_()` using structured fields / `error_key`; falls back to `r.message`. Both bomb call sites (throwBomb, confirmBomb) use it. Toast color logic unchanged (`result.hit ? 'success' : 'error'`).
3. Translations: new `toast.*` block + `error.{game_paused_resumes, already_bombed, target_destroyed, team_doesnt_exist, target_doesnt_exist}` in en.json + nl.json.
4. Verify: `uv run ty check app`, `uv run pytest tests/`, Playwright probe `?lang=nl`, E2E subset.
5. Deploy: `docker compose build app && up -d app`.
6. Review section in tasks/todo.md.

## Tasks
- [x] Backend: structured fields + error_key in routes.py bomb branch; `_check_game_paused` gains error_key/minutes
- [x] Frontend: `bombToastText` helper + 2 call sites in team.html
- [x] Translations: toast block + error keys in en.json + nl.json
- [x] Tests: tests/test_bomb_response.py (hit/sunk/target_name/coord/bombs_left fields, already_bombed error_key)
- [x] Verify: ty check + unit tests pass (140 passed)
- [ ] Playwright probe (`?lang=nl`) for Dutch toast text
- [ ] E2E subset re-run
- [ ] Deploy + review section

## Review (v4)
