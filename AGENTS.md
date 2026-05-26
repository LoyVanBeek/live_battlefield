Here is the full md file content:

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One tack per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimat Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

## Running E2E Tests

E2E tests use Playwright to drive a headless Chromium against a dedicated test stack.

### Quick start
```bash
# Build and start the test infrastructure (fresh DB each time)
docker compose up -d test-postgres test-app

# Wait for app to be ready, then run tests
docker compose run --rm test-e2e

# Or run a specific test file
docker compose run --rm test-e2e pytest tests_e2e/test_gm_page.py -v --video=on-fail

# Clean up everything (deletes test DB volume)
docker compose down -v
```

### What it tests
- `test_gm_page.py` — GM panel page load, team creation, AI players, auto-place, remove, start/end game
- `test_team_page.py` — Team board page load, auto-place ships, remove ship
- `test_locations_page.py` — Locations table/map rendering, add location
- `test_navigation.py` — Cross-page navigation (GM → locations, GM → events)
- `test_complete_game.py` — Full playthrough: create teams → place ships → create locations → start game → play moves → end game

### Architecture
- `tests_e2e/conftest.py` — Fixtures: `seeded_game` (fresh game via API), `seeded_game_with_teams` (game + 2 teams + ships + locations)
- `tests_e2e/pages/` — Page Object Model classes for each page
- Tests run against a separate `test-app` container with its own `test-postgres` database (`battleship_test`)
- `--video=on-fail` saves Playwright video of failed tests to `test-results/`
