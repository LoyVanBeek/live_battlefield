# AGENTS.md - Agent Guidelines for Live Battlefield

This file provides guidance for AI agents working on this codebase.

## Build, Test, and Development Commands

### Running the Application

```bash
# Start all services (PostgreSQL, pgAdmin, app)
docker compose up --build

# Start only the app (if database is running)
docker compose up app

# Rebuild and start fresh
docker compose down -v && docker compose up --build
```

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run a single test file
python3 -m pytest tests/test_telegram_handlers.py -v

# Run a single test function
python3 -m pytest tests/test_telegram_handlers.py::TestHandleJoin::test_new_user_can_join -v

# Run tests with coverage
python3 -m pytest tests/ -v --cov=app --cov-report=html

# Run tests in watch mode (reruns on file changes)
python3 -m pytest tests/ -v --watch
```

### Running Locally (without Docker)

```bash
# Install dependencies
uv pip install --system -r pyproject.toml

# Run database migrations
alembic upgrade head

# Run the bot and server
python3 -m app.main
```

### Linting and Type Checking

```bash
# Install linting tools (if added)
pip install ruff mypy

# Run ruff linter
ruff check app/ tests/

# Run ruff formatter check
ruff format --check app/ tests/

# Run mypy type checker
mypy app/
```

### Database Management

```bash
# Access PostgreSQL container
docker exec -it live-battlefield-postgres-1 psql -U postgres -d battleship

# Access pgAdmin (http://localhost:5050)
# Email: admin@example.com, Password: admin
```

---

## Code Style Guidelines

### Import Organization

Organize imports in the following order, separated by blank lines:

1. **Standard library** - `import os`, `import json`, etc.
2. **Third-party packages** - `from fastapi import...`, `from telegram import...`
3. **Application modules** - `from app.game import...`, `from app.models import...`

```python
# Good
import logging
import os
from typing import Optional

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ContextTypes

from app.game.state import GameState
from app.models import get_player_by_chat
from app.events import save_event
```

### Type Hints

- **Always use type hints** for function parameters and return types
- Use `Optional[X]` instead of `X | None` for compatibility

```python
# Good
async def get_player(db: AsyncSession, chat_id: int) -> Optional[Player]:
    ...

def process_state(state: GameState) -> Dict[str, TeamState]:
    ...

# Avoid
async def get_player(db, chat_id):  # No types
    ...
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `GameState`, `TeamJoinedEvent`)
- **Functions/methods**: `snake_case` (e.g., `handle_join`, `place_ship`)
- **Variables**: `snake_case` (e.g., `team_color`, `bombs_remaining`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `SHIP_SIZES`, `TEAM_COLORS`)
- **Files**: `snake_case.py` (e.g., `ship_placement.py`, `event_saver.py`)

### Async/Await Patterns

- Use `async def` for all functions that perform I/O operations
- Always `await` async calls - never use `.result()` or `.wait()`
- Use `AsyncSession` for database operations
- Mock async functions with `AsyncMock` in tests

```python
# Good
async def handle_join(db: AsyncSession, update: Update, team_name: str) -> str:
    player = await get_player_by_chat(db, update.effective_chat.id)
    ...

# Avoid
def handle_join(db, update, team_name):  # Not async for I/O
    player = get_player_by_chat(db, update.effective_chat.id).result()
```

### Error Handling

- Use descriptive error messages
- Return user-friendly messages from handlers
- Log errors with appropriate level
- Don't expose internal details to users

```python
# Good
if team_color not in state.teams:
    logger.warning(f"Team {team_color} not found")
    return f"Team {team_color} doesn't exist!"

# Avoid
if team_color not in state.teams:
    raise ValueError("Team missing from state dict")  # Exposes internals
```

### Docstrings

Use Google-style docstrings for functions:

```python
async def place_ship(
    db: AsyncSession,
    team_color: str,
    ship_type: str,
    row: int,
    col: int,
    direction: str
) -> tuple[bool, str]:
    """Place a ship on the game board.

    Args:
        db: Database session
        team_color: Color of the team placing the ship
        ship_type: Type of ship (airplane_carrier, battleship, etc.)
        row: Starting row (0-9)
        col: Starting column (0-9)
        direction: 'horizontal' or 'vertical'

    Returns:
        Tuple of (success: bool, message: str)
    """
    ...
```

### Database Patterns

- Use SQLAlchemy ORM with async sessions
- Always use `async with async_session_maker() as session:`
- Commit changes explicitly with `await db.commit()`
- Use dependency injection for database in FastAPI routes

```python
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

@app.get("/teams")
async def get_teams(db: AsyncSession = Depends(get_db)):
    teams = await get_all_teams(db)
    return teams
```

---

## Testing Guidelines

### Test Structure

- Place tests in `tests/` directory
- Name test files as `test_<module>.py`
- Use `pytest` with `pytest-asyncio`
- Use `unittest.mock` with `AsyncMock` for async functions

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_handle_join_creates_player():
    mock_update = MagicMock()
    mock_update.effective_chat.id = 12345
    
    with patch("app.bot.handlers.get_player_by_chat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        # ... rest of test
```

### Test Coverage

- Write tests for all Telegram handlers (see `tests/test_telegram_handlers.py`)
- Test event models and state changes
- Test API endpoints
- Aim for meaningful coverage of core logic

---

## Project Architecture

### Event-Driven Design

The game uses an event-sourcing pattern:
- All game state changes are captured as `Events`
- Events are stored in the database
- `GameState` is rebuilt by replaying all events

Event types:
- `TeamJoinedEvent` - Player joins game
- `ShipPlacedEvent` - Ship placed on board
- `BombThrownEvent` - Bomb thrown at target
- `CodeRedeemedEvent` - Location code redeemed
- `GameStartedEvent` / `GameEndedEvent` - Game state transitions

### Telegram Handler Pattern

Handlers follow this pattern:
1. Extract user input from `Update` and `Context`
2. Load current game state from database
3. Validate input
4. Create and save event
5. Return user-friendly response

```python
async def handle_bomb(
    db: AsyncSession,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_color: str,
    coordinate: str
) -> str:
    # 1. Extract input
    chat_id = update.effective_chat.id
    
    # 2. Load state
    events = await get_all_events(db)
    state = GameState.from_events(events)
    
    # 3. Validate
    if target_color not in state.teams:
        return f"Team {target_color} not found!"
    
    # 4. Create and save event
    event = BombThrownEvent(...)
    await save_event(db, event.to_game_event())
    
    # 5. Return response
    return f"You bombed {target_color}!"
```

---

## TODO Items and Planning

### Where Plans Are Stored

All feature plans are in `docs/plans/`. Each plan is a markdown file:
- `todo-6-animation.md` - Replay mode animation
- `todo-13-disable-buttons.md` - Disable invalid buttons
- `todo-21-admin-auth.md` - Admin panel authentication
- etc.

### How to Plan New Features

1. Check `docs/TODO.md` for remaining items
2. Create a plan in `docs/plans/todo-NN-feature-name.md`
3. Include:
   - Overview of the feature
   - Current state (what exists)
   - Implementation steps with code examples
   - Files to modify/create
   - Testing approach
4. Update `docs/TODO.md` to link the plan

### Plan Template

```markdown
# Plan: Feature Name

## Overview
Brief description of the feature.

## References
- Original TODO: docs/TODO.md item #

## Current State
What currently exists.

## Implementation Plan

### Step 1: Description
Code examples and implementation details.

## Files to Modify
- List of files

## Files to Create
- New files to create

## Testing
How to verify it works.
```

---

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
- **Test First**: When fixing bugs or adding features, write tests first.
- **Verify Before Done**: Run tests, check logs, demonstrate correctness before marking complete.
