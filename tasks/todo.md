# Reusable quiz library (save quizzes ahead of time)

## Backend
- [x] Migration `011_add_quiz_templates.py` — `quiz_templates`, `quiz_template_questions`,
      `quiz_template_answers` (relational, mirrors the game quiz tables)
- [x] `app/database.py`: `QuizTemplate`, `QuizTemplateQuestion`, `QuizTemplateAnswer`
- [x] `app/models.py`: `list_quiz_templates`, `get_quiz_template`, `save_quiz_template`
      (upsert/overwrite by name, edit/rename), `delete_quiz_template`
- [x] `app/api/routes.py`: extract `_quiz_validation_error()` and reuse it in
      `POST /api/quiz/questions`; add `GET /api/quiz-templates`,
      `GET /api/quiz-templates/{id}` (admin-or-gm), `POST /api/quiz-templates`
      (admin-or-gm), `DELETE /api/quiz-templates/{id}` (admin only)

## Shared editor
- [x] Extract the quiz question editor into `app/static/js/quiz_editor.js`
      (`createQuizEditor`), owned by both pages; persistence stays page-level
- [x] `game_settings.html` uses the module (game-mode behavior unchanged)

## Frontend
- [x] `game_settings.html`: library dropdown + Load, and "Save as…" (create/overwrite)
- [x] `admin_dashboard.html`: Quiz Library section — list + New/Edit/Delete + full editor
      (name, Rebalance, Save, Export/Import JSON, Add Question)
- [x] Translation keys `quiz_library`, `quiz_library_load`, `quiz_library_save_as` (en + nl)

## Tests / verification
- [x] Unit tests `TestQuizTemplates` (list/create/delete, name required, validation reuse)
- [x] E2E `test_quiz_library.py`: admin author → list → edit/overwrite → delete;
      game-settings Load + Save-as; load the same quiz into a second game
- [x] POMs: `AdminDashboardPage` quiz-library helpers, `GameSettingsPage` load/save-as
- [x] `uv run ty check`, `uv run pytest tests/` (235 passed), `uvx pip-audit`
- [x] Rebuild `test-app` + `test-e2e`; library/quiz E2E as root; full suite as root (59 passed)

## Review
- **Storage**: three relational tables (`quiz_templates` / `quiz_template_questions` /
  `quiz_template_answers`), not a JSON blob. A saved quiz holds questions + per-answer bomb
  values + the correct flag only — no total budget, no enabled flag. `/api/quiz-templates`
  list returns `question_count` and `total_bombs` (Σ per-question max answer), computed on read.
- **Identity = name**: `save_quiz_template` overwrites any existing template with the same
  name; passing `id` updates in place (enables rename). Both paths bulk-delete the old
  rows before inserting the new set.
- **Loading copies**: the game settings `Load` reads the template and copies its questions
  into the game via the existing save flow, so later library edits never mutate live games.
- **Shared editor**: `createQuizEditor` owns question/answer state, rendering, per-answer
  bombs, warnings, rebalance, and JSON import/export. Persistence, the enabled flag, and the
  template name stay in each host page. Every existing game-settings selector
  (`#quiz-questions-list > div`, `#ans-bombs-{qi}-{ai}`, `input[name="correct-{qi}"]`,
  `#quiz-total`, `#quiz-warning-banner`, `#quiz-import-input`) is preserved, so quiz-mode E2E
  keeps passing unchanged.
- **Validation reuse**: `_quiz_validation_error()` is now the single rule (every question
  needs ≥1 answer and ≥1 bomb-yielding answer) shared by the game quiz save and the library
  save, so both reject the same broken shapes.
- **Auth**: list/get/create accept admin or GM (`verify_admin_or_gm`); delete is admin-only
  (`verify_admin`). Delete has a unit test proving a GM token is rejected (404).
- **Migration verified**: `alembic upgrade head`, `downgrade 010`, and `upgrade head` all
  run clean against Postgres. `alembic check` flags only the redundant `ix_*_id` PK indexes,
  the same pre-existing drift as every other table in the repo.
- **Gotcha found**: deleting the template row with the ORM unit of work failed with an FK
  violation (no ORM relationships, so it deleted the parent before the children). Switched to
  ordered bulk `delete()` statements. E2E now covers rename/overwrite and delete.
- **Not done / out of scope**: no delete control in game settings (as specified); no seeding
  of a starter quiz; admin library stays an inline section on the single-page dashboard.

---

# 📍 Insert location at current GPS position (GM locations page)

## Frontend
- [x] `📍 My location` button in `.form-row` + `.btn-myloc` style + hint text
- [x] `addLocationAtMyLocation()`: secure-context guard, locate → POST `count=1, radius_km=0`, toasts

## Tests / verification
- [x] E2E: GPS insert (exact coords), denied permission, insecure-context stub
- [x] `uv run pytest tests/` + `uv run ty check app` + full e2e
- [x] Note in review: works via ngrok HTTPS; only plain LAN HTTP shows the guard toast

## Review
- One tap → `getCurrentPosition({enableHighAccuracy:true, timeout:10s, maximumAge:0})` → `POST /api/quick/create_locations` with `count:1, radius_km:0`, so the row shows the exact fix (`52.5200, 13.4050` in the E2E asserts radius 0 — a default 2km radius would offset it). Success toast includes rounded accuracy (±12m); button shows `📍 Locating…` and is restored in `finally`.
- Guard order: `!window.isSecureContext || !navigator.geolocation` → `GPS needs HTTPS…` toast, no request sent. Error callbacks map codes 1/2/3 → denied / unavailable / timeout toasts.
- **E2E secure context**: the test origin `http://test-app:8000` is *not* potentially trustworthy (only loopback is, without TLS), so the guard fired for every test. Chromium's `--unsafely-treat-insecure-origin-as-secure` flag is dead in Chrome 153 (verified: `isSecureContext` stays false), and self-signed HTTPS on `test-app` would break every `httpx` fixture (cert verification). Fix: `tests_e2e/conftest.py` now relays `APP_URL` (`http://localhost:8000`, set in `docker-compose.e2e.yml`) to `APP_UPSTREAM` (`test-app:8000`) over a stdlib TCP relay — loopback is secure by default, no flags, no certs.
- **Relay perf bug (found via 3 regressions)**: the naive relay added ~43ms/request (Nagle + delayed-ACK) which flipped three racy "assert right after page load" tests (`test_join_page_loads`, `test_full_color_block`, `test_navigate_to_events_from_gm`). Fixed at the root with `TCP_NODELAY` on both sockets → back to 4–5ms, identical to direct. Page-object/API call sites untouched.
- Production unaffected: the guard, button and toast are client-side only; ngrok already serves real HTTPS (geolocation works there today). Only plain-LAN `http://IP` shows the guard toast.

## Follow-up (not started)
- [ ] HTTPS for plain-LAN HTTP deployments (e.g. local CA / `mkcert` behind the app, or always-ngrok) so phones on `http://IP` get GPS too

---

# Quest Locations Map link on the team page

## Backend
- [x] `team_page` passes `game_id` to the template context (`routes.py`, team.html context)

## Frontend
- [x] 🗺️ button in `.team-actions` header row (always visible, `target="_blank"`)
- [x] Link under the Redeem Code form (renders when started, `#actions`)
- [x] Translation key `action.code.map_link` in en.json ("🗺️ Quest Locations Map") + nl.json ("🗺️ Kaart met questlocaties")

## Tests / verification
- [x] `tests/test_translations.py` — en/nl key-parity (233 keys, currently identical) + map_link non-empty
- [x] E2E: `test_map_link_in_header` (href/target/rel/translated title) + `test_map_link_in_redeem_form` (started game, waits for `#code-loc`)
- [x] `uv run pytest tests/` → 219 passed; `uv run ty check app` → clean
- [x] Rebuilt both `test-app` + `test-e2e`; targeted run → 7 passed; **full suite → 49 passed, 0 failed**
- [x] Live smoke on :8001 — header anchor + JS-built anchor render with real UUID; `accept-language: nl` and `lang=nl` cookie both yield "🗺️ Kaart met questlocaties"

## Review
- `game_id` was already computed in the route but never passed down — one context line,
  nothing else backend-side.
- Link appears in two places per your choice: header button (always) and redeem form
  (only when `gameStatus === 'started'`, matching when the form and map pins exist).
- Both open in a new tab (`rel="noopener"`) so teams keep the team page while reading codes.
- Header anchor gets inline `background:#0f3460;color:#00d9ff;text-decoration:none` —
  `.btn` has no default background and plain `<a class="btn">` would render as a bare link.
- Redeem link is injected into the JS-built HTML with `{{ game_id }}` — Jinja renders
  inside `<script>` (same pattern as `map.html`'s `GAME_ID`), verified in served HTML.
- New translation-key-parity unit test guards future i18n drift (en/nl were already in
  exact sync at 233 keys).
- **Note**: language precedence on `/team/{token}` is query > cookie > accept-language
  (cookie wins) — pre-existing behavior, hit while smoke-testing NL labels.

---

# Numbered location pins on both maps

## Assets
- [x] `app/static/location-pin.css` — teardrop pin (rotated square, `border-radius: 50% 50% 50% 0`), number counter-rotated upright
- [x] `app/static/location-pin.js` — `locationPinIcon(number)` → `L.divIcon`, `iconSize: [30, 36]`, `iconAnchor: [15, 36]` (rotated tip lands at y≈36.2, so the pin points at the exact coordinate — default divIcon anchor is top-left and would offset it)

## Templates
- [x] `locations.html` (GM): assets linked after Leaflet; icon in `updateMarkers()` + map-click-create path
- [x] `map.html` (player): assets linked; icon added alongside existing `title: 'Location #N'`

## Tests / verification
- [x] E2E `test_map_pins_show_location_number` (GM: pins carry 1..5, count == row count)
- [x] E2E `tests_e2e/test_map_page.py`: numbered pins after start + `title` kept; no pins while WAITING (regression) — first coverage for `/map`
- [x] `uv run pytest tests/` → 217 passed; `uv run ty check app` → clean (backend untouched)
- [x] Rebuilt **both** `test-app` and `test-e2e` images; locations + map tests → 17 passed
- [x] Full e2e suite → 47 passed, 0 failed (includes marker-drag test against new pin geometry)

## Review
- **Frontend-only**: no API, event, or migration changes — both endpoints already return `loc.number`.
- Shared assets so GM and player pins can't drift; served by the existing `/static` mount
  (`routes.py:239`), no plumbing.
- Pin is a divIcon: keeps `.leaflet-marker-icon` (so `marker_count`, coords drag-while-editing,
  and `marker.locationNumber` lookups still work — verified by the passing drag test).
- The number sits in an inner span counter-rotated `+45deg` so it stays upright.
- `/map` had zero coverage; added a positive test (started game) and a negative one (waiting
  game renders no pins — `map.html` early-returns on `status === 'waiting'` and never polls).
  The negative test waits on `#game-status-badge` = WAITING so it can't pass vacuously.
- **Gotcha**: `test-results/` flipped to root ownership again mid-session (timestamp 19:16,
  right after a `docker compose run -v` screenshot run) → 47 permission errors; fixed with
  `docker run --user 0 ... chown -R 1000:1000`. Check `ls -ld test-results` before any
  full e2e run.
- Screenshot for visual check: `/tmp/opencode/pin_gm.png` (script `/tmp/opencode/pin_shot.py`).

---

# Editable location coordinates

## Backend
- [x] Endpoint `POST /api/quick/set_location_coords` (finite + range guards, DB-only)

## Frontend
- [x] Clickable coords cell → `coords` branch in `startEdit`/`saveEdit`
- [x] Map click fills input while coords editing (else creates location as before)
- [x] Marker drag enabled only while coords editing; dragend fills input

## Tests / verification
- [x] Unit tests: `TestSetLocationCoordsGuards` (7 tests)
- [x] E2E: 5 new tests (input edit, map click, invalid, marker drag, create-regression)
- [x] `uv run pytest tests/` → 217 passed; `uv run ty check app` → clean
- [x] E2E full suite → 44 passed, 0 failed
- [x] Live API smoke: move ✓, bad lat ✓, `1e400` overflow ✓, unknown loc ✓, state reflects new coords ✓

## Review
- **DB-only, no event/migration**: `GameState` only tracks `location_codes` and
  `location_counter` — `LocationAddedEvent.apply()` ignores lat/lon, and nothing does
  proximity math. Redemption is code-based, so unlike codes this needs no event sourcing.
- The coords cell keeps `data-lat`/`data-lon` from the API so the editor opens with full
  precision while the cell displays `toFixed(4)`.
- Map interactions are gated on `editing?.field === 'coords'`:
  - map click → fills input (editor closed → still creates a location, regression-tested)
  - `marker.dragging.enable()` only for that one marker, `disable()` + `off('dragend')`
    on save/cancel; `dragend` fills the input, saving stays explicit via 💾
- The `#map-hint` overlay switches text during picking so the create-vs-pick mode is
  visible.
- Guard style matches `create_locations`: `math.isfinite` + range checks. Note JSON has
  no NaN/inf literal — the realistic bad input is an overflowing number (`1e400`), which
  is how the unit test exercises that branch.

---

# Default bomb count per game (default 10)

## Backend
- [x] Migration `010_add_default_location_bombs.py` (games.default_location_bombs INT NOT NULL DEFAULT 10)
- [x] `Game.default_location_bombs` column in `app/database.py`
- [x] Endpoint `POST /api/quick/set_default_bombs` (validate >= 1)
- [x] Add `default_bombs` to `/api/admin/locations` response
- [x] Replace `max(1, 100 // total)` in `routes.py` create + bot create/list

## Frontend
- [x] Inline click-to-edit "Default: 💣 N" next to ➕ Add Locations heading

## Tests / verification
- [x] Unit tests: `TestDefaultLocationBombs` (7 tests — column default, validation, create uses game default, fallback)
- [x] E2E: 3 new tests (shown as 10 / set 25 → new location 💣 25 / reject 0)
- [x] `uv run pytest tests/` → 210 passed; `uv run ty check app` → clean
- [x] E2E full suite → 39 passed, 0 failed
- [x] Live API smoke test: default 10 → create 10 → set 25 → reject 0 → create 25, existing location untouched
- [x] Alembic chain verified on scratch DB: `001 → 010` upgrade + `010 → 009` downgrade

## Review
- **Scope guarantee**: changing the default never touches existing locations — only
  `create_locations` (API + bot) reads `game.default_location_bombs`.
- `default_bombs` rides on `/api/admin/locations`, which `loadLocations()` already polls,
  so the header stays in sync with no extra request. It's set before the empty-table
  early-return so the value shows even with zero locations.
- The header editor has its own state (`defaultEditing`) separate from the table's
  `editing`, with `event.stopPropagation()` on its 💾/✕ buttons — same bubbling bug that
  affected the cell editors.
- Bot list display ("Worth N bombs each by default") now compares against the game
  default instead of recomputing `100 // total`.
- `test-results/` ownership got reset to root by `docker compose down -v`; chowned back
  to 1000:1000. If e2e runs suddenly show 39 `PermissionError`s, that's why.

---

# Editable bomb count & code on Locations page

## Backend
- [x] New `LocationCodeChangedEvent` in `app/events/models.py` (apply + to_game_event + AnyEvent union)
- [x] Register event type: `app/events/types.py`, `app/database.py`, `factory.py`, `saver.py`, `__init__.py`
- [x] Migration `009_add_location_code_changed.py` (`ALTER TYPE eventtype ADD VALUE`)
- [x] New endpoint `POST /api/quick/set_location_code` in `app/api/routes.py`
- [x] Stop rebalancing: remove loops in `routes.py` create/remove + fix messages
- [x] Stop rebalancing in `app/bot/handlers.py` create path + fix message

## Frontend
- [x] `app/templates/locations.html`: click-to-edit Code & Bombs cells (startEdit/saveEdit/cancelEdit)
- [x] Add `showToast()` + toast element/CSS, use for new edit flows

## Tests / verification
- [x] Unit test: LocationCodeChangedEvent apply + factory round-trip (`tests/test_location_code_changed_event.py`)
- [x] Unit test: `set_location_code` validation guards (`tests/test_api.py::TestSetLocationCodeGuards`)
- [x] E2E: extended locations page object + 4 new edit tests
- [x] `uv run ty check app` → All checks passed
- [x] `uv run pytest tests/` → 203 passed
- [x] E2E full suite → 36 passed, 0 failed

## Review

### What shipped
- GM can now edit a location's **code** and **bomb count** inline on the locations table
  (click cell → edit → 💾 save / ✕ cancel, Enter/Esc). Works in any game status.
- Code edits are event-sourced via new `LocationCodeChangedEvent` (migration 009), so
  redemption validates against the event-derived state, not just the DB row.
- Bomb-value rebalancing on create/remove removed — existing locations keep their value;
  new locations still get `max(1, 100 // total)`.
- New edits use `showToast()`; existing alert()/confirm() flows untouched.

### Bugs found & fixed during E2E debugging
1. **Cancel re-opened the editor**: the ✕/💾 click bubbled up to the cell handler that
   `cancelEdit()` had just re-armed synchronously → `startEdit()` ran again.
   Fixed with `event.stopPropagation()` on both buttons.
2. **Flaky toast assertions**: `page.wait_for_load_state("networkidle")` returned the
   state already latched by `goto()`, so tests read the toast before the fetch resolved.
   Fixed in `LocationsPage.save_cell_edit()` to wait on the real signal (toast text
   change; on success also editor close + networkidle), with `expect="success"|"error"`.

### Environment note
- `test-results/` host dir was `root:root` (from an earlier root-run Docker volume) while
  the e2e container runs as uid 1000 → 36 teardown `PermissionError`s. Fixed by chown to
  1000:1000; not related to this change.
- `test_complete_game.py::test_play_full_game` failed once (start button race), passes
  on re-run — pre-existing flakiness, not caused by this change.

### Verification
- Unit: 203 passed. Type check: clean. E2E: 36/36 passed (locations page 6/6).

## CI green: type checks, pip-audit, auto-place dead ends

### Review
- **Red CI runs 161–164** (`Run type checks`): CI/pre-commit run `uv run ty check` repo-wide while
  AGENTS.md only documented `ty check app`, which skips tests/. Fixed both diagnostics (c0de885):
  a no-op `game_id` assignment to a SQLAlchemy descriptor, and a mypy-style `# type: ignore[…]`
  that ty doesn't honour (replaced with a `cast`). AGENTS.md now documents the full CI sequence.
- **Hooks were never installed** — `.pre-commit-config.yaml` existed but `.git/hooks/` had only
  `*.sample`, so nothing guarded a single commit. Installed (`pre-commit install`) and documented.
- **Audit step**: `uv lock --upgrade-package anyio` → 4.12.1 → 4.14.2 (PYSEC-2026-4024/4025).
  uv picks 4.14.2 over 4.15.1 because 4.15.1 needs `typing_extensions>=4.16.0` and the lock pins
  4.15.0; a single-package upgrade deliberately leaves the rest alone.
- **Auto-place dead ends**: greedy draw gave up instead of redrawing when an earlier ship left no
  legal cell (3.5% of draws) → HTTP 200 `success:false` → GM Start button stuck disabled → the
  intermittent full-suite E2E failures. `find_placements()` now redraws (bounded, 20 draws).
- Known follow-up (not fixed): `routes.py:2068` and `bot/handlers.py:628` ignore the auto-place
  result and always reply "Ships auto-placed" — truthful now, but unguarded if a board is truly unfillable.

### Verification
- `uv run ty check` repo-wide clean; `uv run pytest tests/` **223 passed** (219 + 4 new in
  `tests/test_ship_placement_service.py`); `uvx pip-audit` exit 0 ("No known vulnerabilities found")
- Placement stress: single draws dead-end 3.5% → `find_placements` 0/1500 failures, mean 0.75ms
- Full E2E: **52/52 passed** (first fully green run; previous runs failed ~every other time)
- CI on `f611fcb`: runs #167/#168 **success** — type checks, tests and audit all pass, and the
  `e2e` job ran for the first time ever (previously always skipped) and passed

---

# Quiz page flicker during a running game (team.html)

## Root cause
- Not page reloads — the team page never reloads itself (`window.location.reload()` exists
  only in join.html). The quiz lives in team.html as `#quiz-section` → `#quiz-content`.
- Every saved event broadcasts (`app/events/saver.py:62` `manager.broadcast("refresh")`; also
  pause/resume `routes.py:2413/2435`). Each SSE push → `renderState()` → `renderActions()`,
  which ended with `actionsEl.innerHTML = html` — destroying the whole actions panel and
  re-creating `#quiz-content` with the literal "loading…" placeholder, then `updateQuizSection()`
  awaited a `/api/quiz/questions` round trip before repainting. That flash was the flicker.
- Same mechanism wiped a typed bomb coordinate and reset the chosen `#target-team` (also rebuilt
  every push). The boards were already fine (`renderGrid` is incremental via `boardGridCache`).

## Fix
- `renderActions()`: rebuild only when the panel's shape changes (`gameStatus | quizEnabled |
  isPaused`); same-shape pushes only refresh ship inventory (preparing) / target teams + quiz
  (started). `renderTargetTeams`/`updateQuizSection` guard their own DOM writes.
- `updateQuizSection()`: writes only when a content signature (question id + text + answer ids)
  changes; the "loading…" placeholder now shows only when `#quiz-content` is empty (first load).
- `renderTargetTeams()`: rebuilds only when the opponent set changes and preserves the chosen value.

## Tests / verification
- E2E regression test `test_quiz_section_not_rebuilt_on_game_events` (test_quiz_mode.py):
  tags the quiz button, installs a MutationObserver on `#quiz-content`, picks a bomb target,
  fires an opponent bomb via the API (broadcasts to the team page), then asserts the button
  element survived (identity), zero child mutations, and the target select kept its value.
- Prove-it-ran: test **fails against the old template** (`quiz text is now: 'ParisLondon'`,
  probe lost) and passes with the fix — it's a real regression test.
- `uv run ty check` repo-wide clean; `uv run pytest tests/` **223 passed**; `uvx pip-audit` exit 0.
- Full E2E: **53/53 passed** (52 + 1 new; quiz tests 2/2).
- Note: the e2e container's compose flag is `--video=on` (AGENTS.md's `--video=on-fail` is
  rejected by the container's pytest-browser; use `retain-on-failure` if wanted) — doc drift,
  not fixed here.

---

# Quiz can be saved with zero bomb-yielding answers (settings editor)

## What broke
- `saveQuiz()` auto-distributed `perQ = Math.floor(total / #questions)` to every correct
  answer. With total < #questions → perQ = 0 → every answer saved with 0 bombs. No UI
  warning, no server validation (`routes.py` `save_quiz_questions` accepted anything).

## Fix (user choice: strict block; auto-fix-to-1 explicitly rejected)
- `game_settings.html`:
  - live `updateQuizWarnings()` — red banner when total < #questions or a question has
    no answers; all question cards get a red outline (`outline`, not `border` — no layout
    shift); re-runs on `#quiz-total` input and after every `renderQuizQuestions()`
  - `saveQuiz()` blocks **before either API call** with an error toast naming the problem
- `routes.py` `POST /api/quiz/questions`: backstop for import/API/bot writes — rejects any
  question with zero answers or zero answers worth 1+ bombs, message names the offending
  question index (+ first 40 chars of its text), 200 + `success:false` per app convention
- Honest bomb display: the editable per-answer bomb input was overwritten on save (correct
  → perQ, others → 0), i.e. a lie. Replaced with a read-only per-answer "N 💣" label
  (green on the bomb-yielding answer(s), grey 0 elsewhere), recomputed from
  `Math.floor(total/questions)` at render, red when it would be 0. POM `add_question`
  stopped filling a bomb input that no longer exists.

## Verification
- Unit: 4 new `TestQuizMode` tests — all-zero answers rejected (names the question),
  empty-answers rejected, broken question among valid ones rejected (names `Question 2`),
  valid set accepted (route awaits model once). `tests/` → **227 passed**
- E2E (3/3 quiz): new `test_quiz_save_blocks_low_total_bombs` — 3 questions, total 2 →
  banner shows "lower than the number of questions", save → error toast, `GET
  /api/quiz/questions` still `[]`. **Proven red against the pre-fix template**
  (timeout on the missing banner) before landing
- `uv run ty check` repo-wide clean; `uvx pip-audit` exit 0
- Full E2E: **54/54 passed** (53 + 1 new), run as root so the video-artifact teardown
  errors don't mask anything (see pre-existing quirk below)

## Pre-existing quirk, not introduced here
- The e2e suite ships `--video=on` + `./test-results:/app/test-results` while the
  container runs as UID 1000. On a per-container-recreated mount nothing writes until
  teardown, and the first write fails with `PermissionError` (mount is root-owned) —
  so every test reports PASS + teardown ERROR, exit 1. That is why CI marks the e2e job
  `continue-on-error`. Wiped `test-results/` locally and verified the same pattern under
  the default (battleship) user; root run → spotless 54/54. Not fixing here.

---

# Quiz import uses JSON bomb values; total = sum of question maxes; rebalance over correct answers

## Frontend (`app/templates/game_settings.html`)
- [x] Import honors per-answer `bomb_value` from the JSON as-is (wrong answers keep their
      values — explicit user choice); auto-fixes any question whose max yield < 1 to 1 on the
      correct answer (user chose auto-fix over block); normalizes to exactly one `is_correct`
      per question.
- [x] Total bomb budget = sum of *each question's max yield* (`questionMaxYield(q)` = highest
      answer bomb value) via `syncQuizTotal()`; the `#quiz-total` input stays editable but is
      re-synced after every change/import/rebalance/save.
- [x] Per-answer rows now show the real stored bomb value (`N 💣`, green when > 0) instead of
      the hardcoded `0 💣`; the per-question "Bombs" field writes to the correct answer.
- [x] Per-answer bombs are **editable** (inline number input per answer, `#ans-bombs-{qi}-{ai}`);
      the per-question "Bombs" field was removed. Editing one answer re-syncs the total (max
      yield per question); correctness is radio-only and never changed by bomb edits.
- [x] Rebalance distributes the budget over the correct answer of every question (wrong
      answers → 0, each correct ≥ 1 even when budget < #questions).
- [x] `saveQuiz()` no longer flattens answer bombs to the per-question value — imported values
      survive a save round-trip; validation (a question must have an answer worth ≥ 1) is now
      derived from answers.
- [x] Management buttons (Rebalance / Save / Export / Import) moved above the questions list;
      "Add Question" stays below the list.

## Backend (`app/models.py`)
- [x] `get_quiz_questions()`: a question's `bomb_value` = max over its answers (was: prefer
      correct-with-bombs, else first bomb-yielding), so the editor's derived total matches the
      API. Route validation on `POST /api/quiz/questions` unchanged (still the save-time backstop).

## Tests / verification
- [x] New E2E `test_quiz_import_uses_json_bomb_values`: imports JSON with 7/2, 3/0, 0 bombs →
      total becomes 11 (7+3+1), wrong answer keeps its 2, zero-yield question auto-fixed to 1;
      asserts Rebalance/Save/Export/Import render above the question list and Add Question below.
- [x] New E2E `test_quiz_edit_answer_bombs`: edits per-answer values (8 on correct, then 3 and 9
      on a wrong answer) → total tracks each question's max (13 → 14), the radio never moves,
      and saved answers keep `(8, correct)` / `(9, wrong)` with question max 9.
- [x] `uv run ty check` repo-wide clean; `uv run pytest tests/` **227 passed**;
      `uvx pip-audit` (uv export, no-dev) exit 0.
- [x] Full E2E as root (avoids the video-teardown permission noise): **56/56 passed**
      (55 + 1 new); quiz file 5/5.

---

# Per-question source links in quizzes (verify the answer after answering)

## Backend
- [x] Migration `012_add_quiz_source.py` — nullable `source_url VARCHAR(1000)` on
      `quiz_questions` + `quiz_template_questions` (with downgrade)
- [x] `app/database.py` + `app/models.py`: `source_url` on `QuizQuestion`/`QuizTemplateQuestion`;
      carried through `get_quiz_questions` / `save_quiz_questions` / `get_quiz_template` /
      `save_quiz_template` (empty → NULL), so library load copies it into games for free
- [x] `app/api/routes.py` `_normalize_source_url()` inside the shared `_quiz_validation_error`:
      trim, empty → None, scheme-less input → `https://`, reject anything not http(s)
      (blocks `javascript:`/`data:`), errors name the question index
- [x] `GET /api/quiz/questions`: team requests get `source_url = None` on unanswered
      questions; GM requests keep full data

## Frontend
- [x] Shared editor (`quiz_editor.js`): per-question source-input row
      (`data-role="source-url"`), change handler, `source_url:''` seed in
      `addQuestion`/`setQuestions`/`importFile`; export picks it up automatically
- [x] `team.html`: `quizPendingResult` state; a just-answered question renders a result
      screen (`#quiz-verdict` Correct/Wrong + `#quiz-correct-answer` + `#quiz-source-link`
      + `#quiz-next`) under the existing `quizContentSignature` no-flicker guard; the active
      unanswered question never renders the link; client-side `^https?://` guard before the
      `<a>`; `target="_blank" rel="noopener noreferrer"`
- [x] `action_quiz` keys `verdict_correct`, `verdict_wrong`, `correct_answer`, `source_label`,
      `next` in en + nl (key-parity test green)

## Tests / verification
- [x] Unit (`tests/test_api.py`): invalid scheme rejected (message names the question);
      `example.com/wiki/France` → `https://example.com/wiki/France`, blank → None;
      team request strips `source_url` from unanswered questions (answered keeps it)
- [x] E2E `test_quiz_source_revealed_after_answer`: link absent pre-answer (and kept out of
      the API payload), result screen shows verdict + correct answer + link, Next advances
      to "All questions answered!"
- [x] `test_quiz_full_flow_browser` updated: each answer now lands on the result screen and
      moves on via Next (was: auto-advance)
- [x] E2E `test_quiz_library_source_round_trips`: author with source → re-open restores it →
      load into a fresh game carries it
- [x] POMs: role-based selectors (`data-role`) in `add_question`/`add_library_question`
      (the new source input shifts text-input indices; also deletes a dead `if False` branch),
      `add_question(..., source_url=)`, TeamPage result-screen helpers
- [x] `uv run ty check` repo-wide clean; `uv run pytest tests/` **238 passed**;
      `uvx pip-audit` exit 0
- [x] Alembic `upgrade head` → `downgrade 011` → `upgrade head` clean against a scratch
      Postgres; both tables show `source_url`
- [x] Full E2E as root on a **fresh** DB (**62/62 passed**, quiz+library 11/11)

## Review
- **Reveal rule**: `source_url` is stripped server-side for unanswered team questions and
  only client-rendered on the result screen of a question the team just answered — two
  independent guards, so the link can't leak via the API payload or the DOM ahead of answering.
- **URL hardening**: a naive "prepend `https://` when there's no `://`" lets
  `javascript:alert(1)` slip through as `https://javascript:alert(1)`; the scheme
  `^[a-zA-Z][a-zA-Z0-9+.\-]*:` check treats a leading scheme as the real one and rejects it.
- **Result screen vs. no-flicker guard**: `updateQuizSection` renders the result branch using
  the existing signature mechanism (`'result|' + id + '|' + ok/no + '|' + source`), so SSE
  refreshes during the result view cause zero DOM churn.
- **`is_correct` leak to unanswered questions is pre-existing and out of scope** — a team
  could read it from the answer payload anyway; not touched here.
- **Follow-up fix (link could vanish)**: the result screen originally rendered the source
  from the refetched question payload. `loadQuizQuestions()` refetches on every call and
  the last-resolving GET wins, so an SSE-triggered refetch that started before the answer
  event committed could land after it, caching the pre-answer snapshot (`source_url: null`)
  and re-rendering the result screen with verdict + correct answer + Next but **no link**.
  Fixed by revealing the source in the `/api/execute` answer response itself (the team just
  answered, so it's policy-legal) and carrying it through `quizPendingResult`; the refetch
  is now just a fallback. Unit test `test_quiz_command_reveals_source_url_in_answer_response`
  proves the server sends it. Full E2E as root on a fresh DB: **62/62**.
- **Env gotcha (again)**: `docker compose -f docker-compose.e2e.yml down -v` errors on the
  shared `live_battlefield_default` network (dev `docker-compose.yml` containers still use
  it), so the `-v` never deletes the test DB volume; `test_select_all_toggles_all` flakes on a
  stale DB. Container recreation via `down` + `up` (no volume is declared for test-postgres)
  is the reliable fresh-DB path. The first full-suite run in this session failed exactly that
  way (61 passed, 1 failed); a genuinely fresh DB → 62/62. Worth a doc fix in AGENTS.md later.

---

# Per-card Edit/Delete buttons in the admin Quiz Library

## What changed
- Every quiz card in `#library-quiz-list` now carries its own `✏️ Edit` and `🗑️ Delete`
  buttons (right-aligned actions div, same pattern as the games list rows). Cards carry
  `data-template-id`; the buttons call `editLibraryQuiz(id)` / `deleteLibraryQuiz(id)`.
- The toolbar's selection-based `✏️ Edit` / `🗑️ Delete` buttons (`#library-edit-btn` /
  `#library-delete-btn`) are **removed** (user choice: per-card is the only path); the
  dropdown + `➕ New` stay. `editLibraryQuiz(id)` syncs the dropdown value to the card, so
  save-after-edit keeps the select consistent.
- POM: `edit_selected_library_quiz` / `delete_selected_library_quiz` → card-based
  `library_card(name)` + `edit_library_quiz(name)` / `delete_library_quiz(name, accept)`.

## Tests / verification
- E2E updates: rename/overwrite/delete and source round-trip tests use card buttons; new
  `test_each_quiz_card_has_edit_and_delete_buttons` (each card has exactly one Edit + one
  Delete; deleting one card leaves the other) — written resilient to sibling tests' templates
  already existing in the DB (assert per-card presence, not a total card count).
- `uv run ty check` clean; `uv run pytest tests/` **239 passed**; `uvx pip-audit` exit 0.
- Full E2E as root on a fresh DB: **63/63 passed** (62 + 1 new; library file 6/6).

## Review
- The delete confirm label still looks the template up via `#library-quiz-select option[value=…]`
  (options stay populated even though the dropdown is no longer the edit/delete trigger).
- `select_library_quiz` POM helper kept — the dropdown still exists and the "Capitals" test
  still selects through it.
- E2E note: this container's pytest-browser rejects `--video=on-fail` (AGENTS.md doc drift,
  already flagged in the flicker section); ran without video flags.

---

# JSON schema for the quiz questions format

## What shipped
- `docs/quiz_questions.schema.json` — draft 2020-12 JSON Schema documenting the
  editor's export/import and API round-trip format:
  - `question_text` (required, non-empty), `bomb_value` (≥0), `source_url`
    (null | empty | `^https?://` only — rejects `javascript:`/`data:` and
    scheme-less strings)
  - `answers` array (min 1) with each answer having `answer_text` (required,
    non-empty), `bomb_value` (≥0), `is_correct` (boolean)
  - `allOf` constraints: ≥1 bomb-yielding answer (`contains` + `bomb_value≥1`),
    exactly one correct answer (`contains` + `is_correct: true` + `maxContains: 1`)
  - `additionalProperties: false` on both question and answer objects (catches typos)
- `jsonschema>=4.18` added to `[project.optional-dependencies] dev`
- 17 unit tests in `tests/test_quiz_schema.py` covering schema validity,
  valid examples (full, minimal, empty array, http), and 12 invalid cases
  (not-array, missing/empty question text, no answers, two correct answers,
  zero bomb yield, javascript: source, data: source, scheme-less source,
  negative bomb value, non-boolean is_correct, unknown property)

## Verification
- `uv run ty check` clean; `uv run pytest tests/` **256 passed** (239 + 17 new);
  `uvx pip-audit` exit 0
- No E2E needed (schema is documentation + unit-tested; no runtime impact)
