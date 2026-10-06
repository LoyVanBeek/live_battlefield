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
