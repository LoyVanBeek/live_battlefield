# Plan: Disable Buttons That Don't Apply

## Overview
Add client-side logic to disable or hide buttons based on current game state (e.g., no bombs = bomb button disabled, all ships placed = place buttons hidden).

## References
- Original TODO: docs/TODO.md item 13

## Current State
- All buttons are always visible and clickable
- User gets error messages when clicking unavailable actions

## Implementation Plan

### Step 1: Update API to return action availability
Modify `app/api/routes.py`:

1. Add endpoint to get current player's action availability:
```python
@app.get("/api/player/{color}/actions")
async def get_player_actions(color: str):
    # Get game state and player state
    # Return:
    # {
    #     "can_bomb": player.bombs > 0,
    #     "can_place_ships": not player.has_all_ships(),
    #     "bombs_remaining": player.bombs,
    #     "ships_placed": player.placed_ship_types,
    #     "ships_total": SHIP_COUNTS
    # }
```

### Step 2: Add button state checking in team page
Modify `app/templates/team.html`:

1. Add helper function to update button states:
```javascript
async function updateButtonStates() {
    const color = document.getElementById('team-select').value;
    if (!color) return;
    
    const response = await fetch(`/api/player/${color}/actions`);
    const actions = await response.json();
    
    // Update bomb button
    const bombBtn = document.getElementById('btn-bomb');
    if (bombBtn) {
        bombBtn.disabled = !actions.can_bomb;
        bombBtn.title = actions.can_bomb 
            ? 'Throw a bomb' 
            : `No bombs remaining (${actions.bombs_remaining} bombs)`;
    }
    
    // Update ship placement buttons
    for (const [shipType, count] of Object.entries(actions.ships_total)) {
        const btn = document.getElementById(`btn-place-${shipType}`);
        const placed = actions.ships_placed[shipType] || 0;
        if (btn) {
            btn.disabled = placed >= count;
            btn.title = `${shipType}: ${placed}/${count} placed`;
        }
    }
}
```

2. Call on page load and after each action:
```javascript
// On page load
document.addEventListener('DOMContentLoaded', updateButtonStates);

// After any action completes
async function handleAction(actionType, ...) {
    await fetch(...);
    await updateButtonStates();
}
```

### Step 3: Add visual feedback styling
```css
button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

button.disabled {
    background: #ccc;
}
```

### Step 4: Apply similar logic to admin page
For start game button:
```javascript
async function checkStartGameButton() {
    const response = await fetch('/api/game-preconditions');
    const data = await response.json();
    
    const startBtn = document.getElementById('btn-start-game');
    startBtn.disabled = !data.can_start;
    startBtn.title = data.cannot_start_reason;
}
```

### Step 5: Consider using CSS for conditional visibility
```css
/* Hide place buttons when all ships placed */
.all-ships-placed .place-ship-btn {
    display: none;
}

/* Show message when no bombs */
.no-bombs .bomb-section {
    opacity: 0.5;
}
```

## Files to Modify
1. `app/api/routes.py` - Add `/api/player/{color}/actions` and `/api/game-preconditions` endpoints
2. `app/templates/team.html` - Add button state checking JavaScript
3. `app/templates/admin.html` - Add preconditions checking

## Files to Create
None

## Testing
1. Join a team with 0 bombs - verify bomb button is disabled
2. Place all ships - verify place buttons are disabled
3. Check start game button when preconditions not met
