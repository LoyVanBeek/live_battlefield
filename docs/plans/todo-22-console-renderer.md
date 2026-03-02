# Plan: Draw Game State to Console on Each Event

## Overview
Create multiple renderers to display game state in different formats (console/ASCII, image, HTML) and integrate them into the event handling flow.

## References
- Original TODO: docs/TODO.md item 22, 23

## Current State
- Image rendering exists (board.py)
- HTML rendering exists (templates)
- No console/ASCII renderer exists
- Renderers not called automatically on events

## Implementation Plan

### Step 1: Create renderers package structure
Create `app/game/renderers/__init__.py`:
```python
from .console import render_console
from .image import render_image
from .html import render_html

__all__ = ['render_console', 'render_image', 'render_html']
```

### Step 2: Create console renderer
Create `app/game/renderers/console.py`:
```python
from app.game.state import GameState, TeamState
from typing import Optional

COLUMN_LABELS = "  A B C D E F G H I J"
ROW_LABELS = "1234567890"

def render_team_board(team: TeamState, private: bool = False) -> str:
    """Render a single team's board to console."""
    lines = []
    lines.append(f"\n=== {team.name} ({team.color}) ===")
    lines.append(f"Bombs: {team.bombs}")
    lines.append(COLUMN_LABELS)
    
    for row_idx, row in enumerate(team.private_board if private else team.public_board):
        row_str = str((row_idx + 1) % 10) + " "
        for col_idx, cell in enumerate(row):
            if private:
                # Show own ships
                row_str += "■ " if cell else "· "
            else:
                # Show attacks from others
                if cell is None:
                    row_str += "· "
                else:
                    attacker, is_hit = cell
                    row_str += "✕ " if is_hit else "○ "
        lines.append(row_str)
    
    return "\n".join(lines)

def render_game_state_console(state: GameState) -> str:
    """Render entire game state to console."""
    lines = []
    lines.append("=" * 50)
    lines.append(f"GAME STATUS: {state.status.value.upper()}")
    lines.append(f"TEAMS: {len(state.teams)}")
    lines.append(f"LOCATIONS: {len(state.location_codes)}")
    lines.append("=" * 50)
    
    for color, team in state.teams.items():
        lines.append(render_team_board(team, private=False))
    
    return "\n".join(lines)

def render_single_board_console(
    state: GameState, 
    team_color: str, 
    private: bool = False
) -> str:
    """Render a specific team's view of the game."""
    if team_color not in state.teams:
        return f"Team {team_color} not found"
    
    team = state.teams[team_color]
    lines = []
    lines.append(f"\n{'='*40}")
    lines.append(f"Board for {team.name}")
    lines.append(f"{'PRIVATE' if private else 'PUBLIC'} view")
    lines.append(f"{'='*40}")
    
    # Show own private board
    lines.append(render_team_board(team, private=True))
    
    # Show other teams' public boards
    for color, other_team in state.teams.items():
        if color != team_color:
            lines.append(render_team_board(other_team, private=False))
    
    return "\n".join(lines)
```

### Step 3: Add console output to event saver
Modify `app/events/saver.py`:
```python
import logging
from app.config import settings
from app.game.renderers import render_game_state_console

logger = logging.getLogger(__name__)

async def save_event(...):
    # existing code...
    
    # Console output (if enabled in config)
    if settings.console_output_enabled:
        state = GameState.from_events([event])
        console_output = render_game_state_console(state)
        logger.info(f"\n{console_output}")
```

### Step 4: Add config option
Modify `app/config.py`:
```python
class Settings(BaseSettings):
    # existing settings...
    console_output_enabled: bool = True
    image_output_enabled: bool = False
```

### Step 5: Create image renderer (if not already integrated)
Ensure `app/game/board.py` has proper integration:
```python
def render_to_logger(state: GameState):
    """Render game state as image and log to file."""
    # Already exists - verify it's being called
    pass
```

### Step 6: Integration with event logging
The console renderer should be called in `app/events/saver.py`:
```python
async def save_event(...):
    # ... existing logic ...
    
    # Log to console after each event
    if settings.console_output_enabled:
        from app.game.state import GameState
        events = await get_all_events(db)
        state = GameState.from_events(events)
        console_view = render_game_state_console(state)
        print(console_view)  # Or use logger
```

## Files to Modify
1. `app/config.py` - Add console_output_enabled setting
2. `app/events/saver.py` - Call console renderer after events

## Files to Create
1. `app/game/renderers/__init__.py`
2. `app/game/renderers/console.py`
3. `app/game/renderers/image.py` (if needed)
4. `app/game/renderers/html.py` (if needed)

## Example Console Output
```
==================================================
GAME STATUS: STARTED
TEAMS: 3
LOCATIONS: 5
==================================================

=== Red Team ===
Bombs: 3
  A B C D E F G H I J
1 · · · · · · · · · 1
2 · ■ ■ ■ ■ · · · · 2
3 · · · · · · · · · 3
...
```

## Testing
1. Trigger an event (place ship, bomb, etc.)
2. Verify console output appears with board state
3. Test with config disabled
