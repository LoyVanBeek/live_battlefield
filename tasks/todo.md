# Reusable location sets + location-quiz library

Decisions (confirmed with the user):
- Both: a reusable location-quiz library AND reusable location sets.
- A saved set restores coords + mode + quiz (full snapshot).
- Location-quiz library is separate from the normal quiz library.
- A set remembers codes and re-applies them verbatim.

## Backend
- [x] Migration `015_add_location_libraries.py`
- [x] `app/database.py`: ORM models (templates, sets)
- [x] `app/models.py`: library + set helpers (mirror quiz templates)
- [x] `app/api/routes.py`: template + set endpoints, save/apply

## Frontend
- [x] `locations.html`: library select/load/save-as + export/import in the quiz modal
- [x] `locations.html`: save-as-set + apply-set controls
- [x] `admin_dashboard.html`: manage both libraries

## Tests
- [x] Unit tests (mirror `TestQuizTemplates`) — 19 pass
- [x] E2E: library load + set snapshot/apply (codes/modes/quizzes restored)
- [x] Fix `game_rows()` scoping so library cards don't inflate select-all count

## Related fix
- [x] `clear-locations` emits removal events (stale `location_codes` fix)

## Results

Local `alembic upgrade head` creates all five library tables. A dev-stack
smoke test (create game → locations + quiz + mode `both` → save set →
apply to a second game) restored the same codes, modes and quiz JSON.

Verified, in the order CI runs them:

1. `uv run ty check` — pass
2. `uv run pytest tests/` — 305 pass (19 new library tests)
3. `uvx pip-audit` against `uv export ...` — no known vulnerabilities
4. `docker compose -f docker-compose.e2e.yml run --rm test-e2e` —
   83 pass (6 new library E2E tests)

Note: locally `--video=on` failed with `PermissionError` writing
`./test-results` (root-owned mount); running the test-e2e container with
`--user root` fixed it. That is an environment issue, not the change.

Commits:
- `cbfb36f` — feature: migration 015, models, routes, UI, tests
- `b29560f` — fix: `clear-locations` removal events

Pushed `feature/quiz_at_locations` to `origin`.

# Unification: one Location Sets library

Follow-up decision (confirmed with the user): drop the separate location-quiz
library and fold quizzes into a single Location Sets library, stored
relationally instead of as a `quiz_json` column.

## Backend
- [x] Migration `015`: only `location_sets`, `location_set_locations`,
      `location_set_questions`, `location_set_answers` (drop the 3
      `location_quiz_template*` tables, drop `location_set_locations.quiz_json`)
- [x] `app/database.py`: drop `LocationQuizTemplate*`, add `LocationSetQuestion` /
      `LocationSetAnswer`
- [x] `app/models.py`: drop location-quiz-template helpers; `save_location_set`
      (create/overwrite), relational read/write helpers, bulk cascade delete
- [x] `app/api/routes.py`: drop `/api/location-quiz-templates*`; add
      `POST`/`PUT /api/location-sets` with validation

## Frontend
- [x] `app/templates/locations.html`: the quiz modal's library row now loads a
      location's quiz from a set (number-matched, with a fallback note) and
      "Save as…" snapshots the whole layout after persisting the open quiz
- [x] `app/templates/admin_dashboard.html`: replace the "Location Quiz Library"
      with a full Location Set editor (locations + per-location quiz modal)

## Tests
- [x] Unit: `TestLocationSetEditor` (POST/PUT validation, normalization, ids)
- [x] E2E: set round-trip via API, modal load-from-set, admin set editor;
      POMs updated

## Verification (CI order)
1. `uv run ty check` — pass
2. `uv run pytest tests/` — 305 pass
3. `uvx pip-audit` against `uv export ...` — no known vulnerabilities
4. `docker compose -f docker-compose.e2e.yml run --rm test-e2e` — 84 pass

Dev DB remediation (revision 015 was already stamped with the old shape):
ran a one-off SQL script that rebuilt `location_set_questions` /
`location_set_answers` from `quiz_json`, then dropped `quiz_json` and the
three template tables. The existing dev set (3 locations, 3 quizzes) survived
and is served correctly by `/api/location-sets`.
