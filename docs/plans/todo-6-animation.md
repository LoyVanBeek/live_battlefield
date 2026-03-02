# Plan: Replay Mode After Game Ends

## Overview
Add an animated replay feature on the admin page that replays the entire game from start to finish after the game ends. Users can watch the progression of events (ships placed, bombs dropped, etc.) with playback controls.

## References
- Original TODO: docs/TODO.md item 6

## Requirements
- Replay starts only after user clicks a button (not auto-start)
- Default speed: 5x (fast forward through events)
- Speed controls: 0.5x, 1x, 2x, 5x, 10x, 2x, 50x buttons
- Event count is limited, so no batching needed

## UI Design

```
┌──────────────────────────────────────────────────────┐
│  🎮 Game Replay                                 [X] │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │                                              │    │
│  │              [BOARD DISPLAY]                 │    │
│  │                                              │    │
│  │     Shows current game state during          │    │
│  │     replay with animations                   │    │
│  │                                              │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ◀ ● ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ▶                │
│  [|<] [▶ Play] [>|]    Speed: [1x] [2x] [5x]    │
│                                                      │
│  Event: Red team threw bomb at Blue (HIT!)          │
│  Time: 00:03:42 / Total: 00:15:30                │
└──────────────────────────────────────────────────────┘
```

## Event Animations

| Event Type | Animation |
|------------|-----------|
| Team Joined | Team card fades in with color |
| Ship Placed | Ship cells fade in sequentially |
| Bomb Thrown | Bomb marker appears, then HIT (red flash) or MISS (gray splash) |
| Code Redeemed | Bomb counter increments with bounce |
| Game Started | "GAME START" overlay |
| Game Ended | Winner banner with confetti |

## Implementation Plan

### Step 1: Add Replay API Endpoint
Modify `app/api/routes.py`:

```python
@app.get("/api/game/replay")
async def get_game_replay():
    """Get all events for replay functionality."""
    async with async_session_maker() as session:
        events = await get_all_events(session)
        
        # Format events for replay
        replay_events = []
        for i, event in enumerate(events):
            replay_events.append({
                "index": i,
                "type": event.event_type.value,
                "payload": event.payload,
                "timestamp": event.created_at.isoformat() if event.created_at else None
            })
        
        settings = await get_game_settings(session)
        
        return {
            "events": replay_events,
            "total_events": len(events),
            "game_status": settings.status.value if settings else "waiting"
        }
```

### Step 2: Create Replay JavaScript Module
Create `app/static/js/replay.js`:

```javascript
class GameReplay {
    constructor(container, boardElement) {
        this.container = container;
        this.boardElement = boardElement;
        this.events = [];
        this.currentIndex = 0;
        this.playing = false;
        this.speed = 5;  // Default 5x
        this.state = this.createInitialState();
    }

    async load() {
        const response = await fetch('/api/game/replay');
        const data = await response.json();
        this.events = data.events;
        this.gameStatus = data.game_status;
        this.renderTimeline();
    }

    createInitialState() {
        return {
            teams: {},
            locationCodes: {},
            currentEvent: null
        };
    }

    play() {
        if (this.currentIndex >= this.events.length) {
            this.currentIndex = 0;
            this.state = this.createInitialState();
        }
        this.playing = true;
        this.tick();
    }

    pause() {
        this.playing = false;
    }

    tick() {
        if (!this.playing || this.currentIndex >= this.events.length) {
            if (this.currentIndex >= this.events.length) {
                this.playing = false;
            }
            return;
        }

        const event = this.events[this.currentIndex];
        this.applyEvent(event);
        this.render();
        
        // Calculate delay based on speed (base 1000ms / speed)
        const delay = 1000 / this.speed;
        
        setTimeout(() => {
            this.currentIndex++;
            this.tick();
        }, delay);
    }

    applyEvent(event) {
        this.state.currentEvent = event;
        
        switch (event.type) {
            case 'team_joined':
                this.state.teams[event.payload.color] = {
                    name: event.payload.name,
                    color: event.payload.color,
                    ships: [],
                    bombs: event.payload.bombs
                };
                break;
                
            case 'ship_placed':
                if (this.state.teams[event.payload.color]) {
                    // Add ship cells to team
                    // Animation will highlight these
                }
                break;
                
            case 'bomb_thrown':
                // Update board with hit/miss marker
                break;
                
            case 'code_redeemed':
                if (this.state.teams[event.payload.color]) {
                    this.state.teams[event.payload.color].bombs += event.payload.bombs_earned;
                }
                break;
                
            case 'game_started':
                this.state.status = 'started';
                break;
                
            case 'game_ended':
                this.state.status = 'ended';
                this.state.winner = event.payload.winner;
                break;
        }
    }

    render() {
        this.updateBoard();
        this.updateTimelinePosition();
        this.updateEventInfo();
    }

    setSpeed(speed) {
        this.speed = speed;
    }

    seekTo(index) {
        // Rebuild state up to this index
        this.currentIndex = index;
        this.state = this.createInitialState();
        
        for (let i = 0; i <= index; i++) {
            this.applyEvent(this.events[i]);
        }
        
        this.render();
    }

    renderTimeline() {
        // Render timeline with event markers
    }

    updateBoard() {
        // Render current board state with animations
    }

    updateTimelinePosition() {
        // Update progress indicator
    }

    updateEventInfo() {
        // Show current event description
    }
}

// Initialize replay
function initReplay() {
    const container = document.getElementById('replay-modal');
    const board = document.getElementById('replay-board');
    const replay = new GameReplay(container, board);
    
    // Load events
    replay.load();
    
    // Attach controls
    document.getElementById('btn-replay-play').addEventListener('click', () => replay.play());
    document.getElementById('btn-replay-pause').addEventListener('click', () => replay.pause());
    document.getElementById('btn-replay-reset').addEventListener('click', () => replay.seekTo(0));
    
    // Speed buttons
    document.querySelectorAll('.speed-btn').forEach(btn => {
        btn.addEventListener('click', () => replay.setSpeed(parseInt(btn.dataset.speed)));
    });
    
    return replay;
}
```

### Step 3: Create Replay CSS Styles
Create `app/static/css/replay.css`:

```css
/* Replay Modal */
#replay-modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.9);
    z-index: 1000;
}

#replay-modal.active {
    display: flex;
    align-items: center;
    justify-content: center;
}

.replay-content {
    background: #1a1a2e;
    border-radius: 16px;
    padding: 24px;
    max-width: 900px;
    width: 90%;
    color: #fff;
}

/* Timeline */
.replay-timeline {
    width: 100%;
    height: 8px;
    background: #333;
    border-radius: 4px;
    margin: 20px 0;
    position: relative;
    cursor: pointer;
}

.replay-progress {
    height: 100%;
    background: linear-gradient(90deg, #4DABF7, #9775FA);
    border-radius: 4px;
    transition: width 0.1s linear;
}

.replay-marker {
    position: absolute;
    top: -4px;
    width: 16px;
    height: 16px;
    background: #FFD700;
    border-radius: 50%;
    transform: translateX(-50%);
}

/* Controls */
.replay-controls {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin: 16px 0;
}

.replay-controls button {
    background: #333;
    border: none;
    color: #fff;
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
}

.replay-controls button:hover {
    background: #4DABF7;
}

.replay-controls button.active {
    background: #9775FA;
}

/* Speed buttons */
.speed-buttons {
    display: flex;
    gap: 8px;
    margin-left: 20px;
}

.speed-btn {
    padding: 4px 12px !important;
    font-size: 12px;
}

/* Board during replay */
#replay-board {
    background: #16213e;
    border-radius: 8px;
    padding: 16px;
    min-height: 400px;
    margin-bottom: 16px;
}

/* Event info */
.replay-event-info {
    text-align: center;
    padding: 12px;
    background: #0f3460;
    border-radius: 8px;
    font-size: 14px;
}

.replay-event-info .event-type {
    color: #FFD700;
    font-weight: bold;
}

/* Animations */
@keyframes shipFadeIn {
    from { opacity: 0; transform: scale(0.8); }
    to { opacity: 1; transform: scale(1); }
}

@keyframes bombHit {
    0% { transform: scale(0); opacity: 0; }
    50% { transform: scale(1.3); }
    100% { transform: scale(1); opacity: 1; }
}

@keyframes bombMiss {
    0% { transform: scale(0); opacity: 0; }
    50% { transform: scale(1.2); }
    100% { transform: scale(1); opacity: 0.7; }
}

.ship-cell-new {
    animation: shipFadeIn 0.5s ease-out;
}

.bomb-hit {
    animation: bombHit 0.4s ease-out;
    background: #e03131 !important;
}

.bomb-miss {
    animation: bombMiss 0.4s ease-out;
    background: #868e96 !important;
}

/* Game start/end overlays */
.replay-overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 48px;
    font-weight: bold;
    text-shadow: 0 0 20px rgba(0,0,0,0.8);
    animation: overlayPulse 1s ease-out;
}

@keyframes overlayPulse {
    from { transform: translate(-50%, -50%) scale(0.5); opacity: 0; }
    to { transform: translate(-50%, -50%) scale(1); opacity: 1; }
}

/* Winner banner */
.replay-winner {
    background: linear-gradient(135deg, #FFD700, #FFA500);
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    animation: winnerAppear 0.5s ease-out;
}

@keyframes winnerAppear {
    from { transform: scale(0.8); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
}
```

### Step 4: Add Replay UI to Admin Page
Modify `app/templates/admin.html`:

```html
<!-- Replay Button (show after game ends) -->
<button id="btn-show-replay" class="hidden" onclick="showReplayModal()">
    🎬 Show Replay
</button>

<!-- Replay Modal -->
<div id="replay-modal">
    <div class="replay-content">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h2>🎮 Game Replay</h2>
            <button onclick="closeReplayModal()" style="background: transparent; border: none; color: #fff; font-size: 24px; cursor: pointer;">×</button>
        </div>
        
        <div id="replay-board">
            <!-- Board will be rendered here -->
        </div>
        
        <div class="replay-timeline" id="replay-timeline">
            <div class="replay-progress" id="replay-progress" style="width: 0%"></div>
        </div>
        
        <div class="replay-controls">
            <button id="btn-replay-reset" title="Reset">|◀</button>
            <button id="btn-replay-play" title="Play">▶</button>
            <button id="btn-replay-pause" class="hidden" title="Pause">❚❚</button>
            <button id="btn-replay-end" title="Go to End">▶|</button>
            
            <div class="speed-buttons">
                <span style="color: #888; margin-right: 8px;">Speed:</span>
                <button class="speed-btn" data-speed="0.5">0.5x</button>
                <button class="speed-btn" data-speed="1">1x</button>
                <button class="speed-btn" data-speed="2">2x</button>
                <button class="speed-btn active" data-speed="5">5x</button>
            </div>
        </div>
        
        <div class="replay-event-info">
            <span id="replay-event-text">Click play to start replay</span>
        </div>
    </div>
</div>

<script src="/static/js/replay.js"></script>
<link rel="stylesheet" href="/static/css/replay.css">
```

### Step 5: Add Replay Trigger Logic
Add to the game status checking JavaScript in admin.html:

```javascript
async function checkGameStatus() {
    const response = await fetch('/api/game-status');
    const data = await response.json();
    
    // Show replay button when game ends
    const replayBtn = document.getElementById('btn-show-replay');
    if (data.status === 'ended') {
        replayBtn.classList.remove('hidden');
    } else {
        replayBtn.classList.add('hidden');
    }
}

function showReplayModal() {
    document.getElementById('replay-modal').classList.add('active');
    initReplay();
}

function closeReplayModal() {
    document.getElementById('replay-modal').classList.remove('active');
}
```

## Files to Modify
1. `app/api/routes.py` - Add `/api/game/replay` endpoint
2. `app/templates/admin.html` - Add replay modal and trigger button

## Files to Create
1. `app/static/js/replay.js` - Replay engine
2. `app/static/css/replay.css` - Animation styles

## Testing
1. Complete a full game with multiple events
2. End the game
3. Click "Show Replay" button
4. Click play and verify animations work
5. Test speed controls
6. Test timeline scrubbing
7. animation at end
 Verify winner