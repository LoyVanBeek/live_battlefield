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
