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
