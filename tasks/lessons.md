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
