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
