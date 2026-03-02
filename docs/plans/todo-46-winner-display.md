# Plan: Make Clear on Admin Page That Someone Won

## Overview
Add prominent winner display on admin page when game ends, showing which team won with visual indicators.

## References
- Original TODO: docs/TODO.md item 46

## Current State
- Game can end when only one team remains
- No visual indication of winner on admin page
- Users must check logs or infer from game state

## Implementation Plan

### Step 1: Add winner detection logic
Modify `app/game/state.py`:
```python
def get_winner(self) -> Optional[TeamState]:
    """Determine the winner of the game."""
    # Get teams that have all ships placed (active players)
    active_teams = [t for t in self.teams.values() if t.has_all_ships()]
    
    # If no active teams, no winner
    if not active_teams:
        return None
    
    # If only one team left (all others destroyed)
    survivors = [t for t in active_teams if not t.is_destroyed()]
    
    if len(survivors) == 1:
        return survivors[0]
    
    # Check if only one team has not been destroyed
    not_destroyed = [t for t in active_teams if not t.is_destroyed()]
    if len(not_destroyed) == 1:
        return not_destroyed[0]
    
    return None  # No winner yet or draw
```

### Step 2: Add game status endpoint
Modify `app/api/routes.py`:
```python
from app.game.state import GameState, GameStatusField
from app.database import GameStatus

@app.get("/api/game-status")
async def get_game_status():
    """Get current game status including winner."""
    async with async_session_maker() as session:
        settings = await get_game_settings(session)
        events = await get_all_events(session)
        
        state = GameState.from_events(events)
        
        # Determine winner
        winner = None
        if settings and settings.status == GameStatus.ENDED:
            winner_team = state.get_winner()
            if winner_team:
                winner = {
                    "name": winner_team.name,
                    "color": winner_team.color
                }
        
        return {
            "status": settings.status.value if settings else "waiting",
            "winner": winner,
            "teams_count": len(state.teams),
            "locations_count": len(state.location_codes),
            "can_start": state.can_start()
        }
```

### Step 3: Add winner banner to admin HTML
Modify `app/templates/admin.html`:

```html
<!-- Winner Banner (hidden by default) -->
<div id="winner-banner" class="hidden" style="
    background: linear-gradient(135deg, #FFD700, #FFA500);
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    margin: 20px 0;
">
    <h2 style="margin: 0; font-size: 2em;">🏆 Game Over! 🏆</h2>
    <p id="winner-text" style="font-size: 1.5em; margin: 10px 0;"></p>
</div>

<!-- Update game status display -->
<div id="game-status-display" style="padding: 10px; margin: 10px 0;">
    <span>Status: <strong id="status-text">waiting</strong></span>
    <span id="winner-display" class="hidden" style="margin-left: 20px;">
        Winner: <strong id="winner-name"></strong>
    </span>
</div>
```

### Step 4: Add JavaScript to detect and display winner
```javascript
async function checkGameStatus() {
    const response = await fetch('/api/game-status');
    const data = await response.json();
    
    // Update status text
    document.getElementById('status-text').textContent = data.status;
    
    // Show/hide winner
    const winnerDisplay = document.getElementById('winner-display');
    const winnerBanner = document.getElementById('winner-banner');
    
    if (data.winner) {
        // Update header display
        document.getElementById('winner-name').textContent = data.winner.name;
        winnerDisplay.classList.remove('hidden');
        
        // Show full banner
        document.getElementById('winner-text').textContent = 
            `${data.winner.name} Wins!`;
        winnerBanner.classList.remove('hidden');
        
        // Add team color styling
        winnerBanner.style.background = getTeamColorGradient(data.winner.color);
    } else {
        winnerDisplay.classList.add('hidden');
        winnerBanner.classList.add('hidden');
    }
    
    return data;
}

function getTeamColorGradient(color) {
    const colors = {
        'red': 'linear-gradient(135deg, #FF6B6B, #EE5A5A)',
        'blue': 'linear-gradient(135deg, #4DABF7, #339AF0)',
        'green': 'linear-gradient(135deg, #51CF66, #40C057)',
        'purple': 'linear-gradient(135deg, #9775FA, #845EF7)',
        'orange': 'linear-gradient(135deg, #FF922B, #FD7E14)',
        'yellow': 'linear-gradient(135deg, #FFE066, #FCC419)'
    };
    return colors[color] || 'linear-gradient(135deg, #FFD700, #FFA500)';
}

// Poll every 5 seconds
setInterval(checkGameStatus, 5000);
```

### Step 5: Add "Not enough teams" handling
Update the logic in the endpoint:
```python
@app.get("/api/game-status")
async def get_game_status():
    # ... existing code ...
    
    winner = None
    no_winner_reason = None
    
    if settings and settings.status == GameStatus.ENDED:
        if len(state.teams) < 2:
            no_winner_reason = "Not enough teams to determine winner"
        else:
            winner_team = state.get_winner()
            if winner_team:
                winner = {
                    "name": winner_team.name,
                    "color": winner_team.color
                }
            else:
                no_winner_reason = "Draw or no winner"
    
    return {
        "status": settings.status.value if settings else "waiting",
        "winner": winner,
        "no_winner_reason": no_winner_reason,
        # ... other fields
    }
```

Update the display:
```javascript
if (data.winner) {
    // Show winner
} else if (data.no_winner_reason) {
    document.getElementById('winner-text').textContent = 
        `Game Ended: ${data.no_winner_reason}`;
    winnerBanner.classList.remove('hidden');
}
```

### Step 6: Add styling for different states
```css
#winner-banner.winner {
    background: linear-gradient(135deg, #FFD700, #FFA500);
    animation: celebrate 1s ease-in-out infinite;
}

#winner-banner.no-winner {
    background: linear-gradient(135deg, #6c757d, #495057);
}

@keyframes celebrate {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.02); }
}
```

## Files to Modify
1. `app/game/state.py` - Improve winner detection logic
2. `app/api/routes.py` - Add /api/game-status endpoint
3. `app/templates/admin.html` - Add winner banner and JavaScript

## Files to Create
None

## Example Output

**When there's a winner:**
```
🏆 Game Over! 🏆
Blue Team Wins!
```

**When not enough teams:**
```
🏆 Game Over! 🏆
Game Ended: Not enough teams to determine winner
```

## Testing
1. Start game with 2 teams
2. Destroy one team manually via API
3. Verify winner banner appears with correct team name
4. Test with < 2 teams scenario
5. Test polling updates
