# Location quiz mode (check-in without posting codes)

Semantics locked with the user:
- No geolocation — honor system; a team answers by picking the location.
- Per-location mode: `code` (default) / `quiz` / `both`.
- Per-question bomb values; one attempt per question (event recorded every attempt).
- A wrong answer still marks the location visited for that team.
- `both` rewards independently (code and quiz can both pay out).

## Backend
- [x] Migration `014_add_location_quiz.py`: `locations.quiz_mode`, `location_quiz_questions`,
      `location_quiz_answers`, enum value `LOCATION_QUIZ_ANSWERED`
- [x] `app/database.py`: `EventType.LOCATION_QUIZ_ANSWERED`, `Location.quiz_mode`,
      `LocationQuizQuestion`, `LocationQuizAnswer`
- [x] `app/events/types.py`: `LOCATION_QUIZ_ANSWERED`
- [x] `app/events/models.py`: `LocationQuizAnsweredEvent` + `AnyEvent`
- [x] `app/events/factory.py`, `saver.py`, `__init__.py`: register the event
- [x] `app/models.py`: `get_location_quiz_questions`, `save_location_quiz_questions`,
      `set_location_quiz_mode`, `get_location_quiz_question_counts`
- [x] `app/api/routes.py`:
  - [x] `location_quiz` command in `/api/execute`
  - [x] `code` command rejects `quiz`-only locations
  - [x] `GET /api/location-quiz/state` (team/GM)
  - [x] `GET`/`POST /api/location-quiz/questions` (GM; reuse `_quiz_validation_error`)
  - [x] `POST /api/quick/set_location_quiz_mode` (GM)
  - [x] `/api/admin/locations`: `quiz_mode` + `question_count`, `visited_by` counts quiz attempts

## Frontend
- [x] `team.html`: location-quiz action group + `updateLocationQuizSection()` etc.
- [x] `locations.html`: mode + Quiz button per row, editor modal reusing `createQuizEditor`
- [x] Translations `location_quiz.*` (en + nl parity)

## Tests
- [x] Unit `tests/test_location_quiz.py` (20 tests)
- [x] E2E `tests_e2e/test_location_quiz.py` + POM helpers (3 tests)
- [x] `uv run ty check`, `uv run pytest tests/`, E2E, deploy, atomic commits

## Bonus fix
- [x] Auto-start race: `asyncio.ensure_future(_auto_start_if_ready(db, ...))` shared the
      request session, which `get_api_db` closes on response. Added
      `_auto_start_if_ready_detached(game_uuid)` that opens its own session; used by the
      `place` command and `quick_place_all_ships`. This was causing a deterministic
      `InterfaceError: another operation is in progress` during E2E ship placement.

## Review
- `uv run ty check` — All checks passed (repo-wide)
- `uv run pytest tests/` — 283 passed
- `uvx pip-audit` — No known vulnerabilities found
- `docker compose -f docker-compose.e2e.yml run --rm test-e2e` — 75 passed
- Hidden-answer semantics covered by `TestLocationQuizState`: `is_correct`/`bomb_value`
  and `source_url` are stripped until the team has answered that question.
- `both` mode verified to reward the code (`TestCodeCommandModeGating`) and the quiz
  (`TestLocationQuizCommand.test_both_mode_location_offers_the_quiz`) independently.
