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
- Commits: `4f85421` backend structured fields + error_key, `aeaffa5` frontend bombToastText + translations, `4cef587` tests, `c9254a1` fix param substitution in guard toasts.
- `uv run ty check app`: pass. `uv run pytest tests/`: 140 passed (3 new in tests/test_bomb_response.py).
- Playwright probe (test-app, `?lang=nl`, real UI bomb clicks): 4/4 —
  - NL miss: "Bombardeerde Blue Team op A1: MIS op A1!. Bommen over: 52"
  - NL hit: "Bombardeerde Blue Team op C1: RAAK op C1!. Bommen over: 51"
  - NL already-bombed guard: "C1 al gebombardeerd!" (caught missing `{coord}` param — fixed in `c9254a1`)
  - EN sanity (fresh context, `?lang=en`): "C1 already bombed!"
- E2E subset (test_team_page, test_complete_game): 4 passed.
- Deployed: `docker compose build app && up -d app`; container serves bombToastText (verified in-image). Test stack torn down.
- Design: `result.message` kept for Telegram bot + other consumers; client falls back to it when `error_key`/structured fields missing (or translation key missing).
- Note: lang selection is cookie-based (server sets `lang` cookie on first visit) — default Accept-Language probing only applies before a cookie exists.

---

# Security review & hardening (hosting prep)

## Plan (approved — "Go tackle the issues")
1. Fix P1 authorization: force `team_color` from auth for team-token calls (execute + quick endpoints).
2. Stored XSS: sanitize names server-side + escape all name interpolation on public/anonymous pages.
3. Fog-of-war: `private.png` requires own team token or same-game GM token.
4. Weak secrets: longer location codes, wider token alphabet, hmac.compare_digest, secrets-based admin token (not logged).
5. Rate limiting on code redeem + join endpoints.
6. `/registergm` gated by optional `GM_SECRET`.
7. Security headers + vendored Leaflet (kill unpkg Referer leak).
8. Dockerfile: non-root user, pinned slim base, no tests/static duplication.
9. Verify: ty, pytest, E2E parity vs baseline, deploy.

## Tasks
- [x] P1.1 auth-color enforcement (routes.py execute + quick place_all_ships/remove_ship)
- [x] P1.2 sanitize_name (app/safety.py) at join/rename/create/rename entry points + esc() in all templates
- [x] P1.3 private.png requires own team_token or same-game gm_token; game_id param removed
- [x] P1.4 generate_location_code(6) + team token alphabet + rate_limit.py (code_attempt_limiter, join_limiter)
- [x] P2 GM_SECRET gate on /registergm; compare_digest in verify_admin/verify_admin_or_gm; token_urlsafe admin token; token log removed
- [x] P2/P3 security_headers middleware + /static mount + vendored Leaflet 1.9.4
- [x] P3 Dockerfile non-root (battleship uid 1000), python:3.11.13-slim, no tests copy; Dockerfile.e2e USER root for setup then battleship
- [x] Tests: tests/test_safety.py + auth-color / private.png regression tests in tests/test_api.py
- [x] Verify: `uv run ty check app` (pass), `uv run pytest tests/` (150 passed)
- [x] Verify: E2E parity — identical 7 failed/25 passed on baseline vs changes (all 7 pre-existing `#join-color` stale-POM failures, unrelated to security work)
- [ ] Commits: step-by-step (authz, XSS/templates, private board auth, tokens/rate-limit/GM_SECRET, headers/leaflet, Docker)
- [ ] Deploy + review section

## Design notes
- `sanitize_name` strips `< > & " '` and caps at 30 chars (matches client maxlength). Escape-only in templates via `esc()`; server-side sanitization is the real defense.
- Team tokens: 9 chars from ascii_letters+digits (~54 bits). Admin token: `secrets.token_urlsafe(24)`.
- Location codes: 6 chars secrets-derived, agnostic to case for verbal sharing; `random.choices` replaced.
- Rate limiter is in-memory per key (game+color for codes, invite token for joins), 10/min; fine for single-Pi deployment.
- `security_headers`: nosniff, X-Frame-Options DENY, Referrer-Policy no-referrer, Cache-Control only when not set (preserves replay GIF public caching).
- Leaflet vendored to app/static/leaflet/ (unpkg no longer referenced → no token leak via Referer).

## Review
- Commits:
  - `0370a2f` fix: force team_color from auth token on team endpoints (execute, place_all_ships, remove_ship)
  - `2691348` fix: sanitize team names server-side and escape all name interpolation in templates
  - `550953e` fix: require team token or same-game GM token for private board PNG
  - `afe0040` fix: strong secrets, rate-limit code/join, and optional GM_SECRET gate for /registergm
  - `e1e3716` feat: security headers, self-hosted Leaflet, and non-root pinned-container Dockerfile
  - `229131b` docs: record security hardening review and lessons
- `uv run ty check app`: pass. `uv run pytest tests/`: 150 passed (23 new security regression tests).
- E2E parity vs baseline: identical 7 failed / 25 passed (7 pre-existing `#join-color` stale-POM failures in test_gm_page/test_full_flow; reproduced on baseline, unrelated to this work).
- Deployed: `docker compose build app && up -d app`; container runs as `battleship` (non-root) uid 1000.
- Live verification (prod, real HTTP):
  - Security headers on all responses (nosniff, DENY, no-referrer, Cache-Control fallback).
  - `/static/leaflet/leaflet.{js,css}` + marker images serve 200 (unpkg no longer referenced).
  - Join with `<script>Red</script> Team` → stored as `scriptRed/script Team` (angle brackets stripped).
  - private.png: 401 with no/invalid token, 200 with own team token.
  - Admin create-game + delete-game work; new token formats live (e.g. `EPG-fAL-4W6`).
  - Join rate limit: 10 allowed, then 429 with clear message.
  - Admin token no longer logged at startup (was leaking to stdout).
- Smoke-test game removed from prod DB afterwards.
- NGROK_AUTHTOKEN/NGROK_DOMAIN are commented out in `.env` → ngrok container can't authenticate (pre-existing config state; Funnel is the chosen tunnel).
