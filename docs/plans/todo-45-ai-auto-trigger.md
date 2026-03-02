# Plan: AI Auto-Trigger

## Overview
Implement automatic AI moves so AI players can act without manual triggering. Uses a background scheduler to periodically execute AI moves.

## References
- Original TODO: docs/TODO.md item 45

## Current State
- AI players exist and can be added via Telegram or admin
- AI moves must be manually triggered via admin panel button
- No automatic execution after server restart

## Implementation Plan

### Step 1: Add APScheduler dependency
Check `pyproject.toml` and add if needed:
```toml
[project.dependencies]
apscheduler = "^3.10.0"
```

### Step 2: Create AI scheduler service
Create `app/services/ai_scheduler.py`:
```python
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional

from app.database import async_session_maker, GameSettings, GameStatus
from app.models import get_all_events, get_all_players
from app.game.state import GameState
from app.services.ai_player import execute_ai_moves as do_execute_ai_moves

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
_enabled: bool = False
_interval_minutes: int = 1  # Run every minute by default


def init_scheduler() -> AsyncIOScheduler:
    """Initialize the scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    """Start the AI scheduler."""
    global _enabled
    scheduler = init_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        _enabled = True
        logger.info("AI scheduler started")
    
    # Schedule the job
    if not scheduler.get_job("ai_moves"):
        scheduler.add_job(
            run_ai_moves,
            trigger=IntervalTrigger(minutes=_interval_minutes),
            id="ai_moves",
            replace_existing=True
        )
        logger.info(f"AI moves scheduled every {_interval_minutes} minutes")


def stop_scheduler():
    """Stop the AI scheduler."""
    global _enabled
    scheduler = init_scheduler()
    
    if scheduler.running:
        scheduler.shutdown()
        _enabled = False
        logger.info("AI scheduler stopped")


def set_interval(minutes: int):
    """Change the interval between AI moves."""
    global _interval_minutes
    _interval_minutes = minutes
    
    scheduler = init_scheduler()
    job = scheduler.get_job("ai_moves")
    if job:
        job.remove()
        scheduler.add_job(
            run_ai_moves,
            trigger=IntervalTrigger(minutes=minutes),
            id="ai_moves",
            replace_existing=True
        )
        logger.info(f"AI moves interval changed to {minutes} minutes")


async def run_ai_moves():
    """Main function that runs on schedule."""
    global _enabled
    
    if not _enabled:
        return
    
    try:
        async with async_session_maker() as session:
            # Check if game is running
            result = await session.execute(
                select(GameSettings).limit(1)
            )
            settings = result.scalar_one_or_none()
            
            if not settings or settings.status != GameStatus.STARTED:
                logger.debug("Game not started, skipping AI moves")
                return
            
            # Check for AI players
            from app.database import Role
            from sqlalchemy import select
            
            result = await session.execute(
                select(Player).where(Player.role == Role.AI)
            )
            ai_players = result.scalars().all()
            
            if not ai_players:
                logger.debug("No AI players, skipping AI moves")
                return
            
            # Execute AI moves
            logger.info("Running scheduled AI moves")
            await do_execute_ai_moves()
            
    except Exception as e:
        logger.error(f"Error running AI moves: {e}")


def is_enabled() -> bool:
    """Check if scheduler is enabled."""
    return _enabled


async def trigger_now():
    """Manually trigger AI moves (for testing/admin)."""
    await run_ai_moves()
```

### Step 3: Integrate scheduler into main.py
Modify `app/main.py`:
```python
from app.services.ai_scheduler import start_scheduler, stop_scheduler

# At app startup
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    start_scheduler()

# At app shutdown
@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()
    # ... existing shutdown code ...
```

### Step 4: Add API endpoints for scheduler control
Modify `app/api/routes.py`:
```python
from app.services.ai_scheduler import (
    start_scheduler, 
    stop_scheduler, 
    is_enabled,
    set_interval,
    trigger_now
)

@app.get("/api/ai/scheduler/status")
async def get_scheduler_status():
    """Get current scheduler status."""
    return {
        "enabled": is_enabled(),
        "interval_minutes": get_interval()  # Need to add this function
    }

@app.post("/api/ai/scheduler/enable")
async def enable_scheduler():
    """Enable automatic AI moves."""
    start_scheduler()
    return {"status": "enabled"}

@app.post("/api/ai/scheduler/disable")
async def disable_scheduler():
    """Disable automatic AI moves."""
    stop_scheduler()
    return {"status": "disabled"}

@app.post("/api/ai/scheduler/interval")
async def set_scheduler_interval(minutes: int = 1):
    """Set interval between AI moves."""
    set_interval(minutes)
    return {"interval_minutes": minutes}

@app.post("/api/ai/scheduler/trigger")
async def trigger_ai_now():
    """Manually trigger AI moves."""
    await trigger_now()
    return {"status": "triggered"}
```

### Step 5: Add admin UI controls
Modify `app/templates/admin.html`:
```html
<!-- AI Scheduler Controls -->
<div class="ai-scheduler-controls">
    <h3>AI Auto-Move Scheduler</h3>
    <div class="control-row">
        <label>
            <input type="checkbox" id="ai-scheduler-enabled">
            Enable Auto AI Moves
        </label>
    </div>
    <div class="control-row">
        <label for="ai-interval">Interval (minutes):</label>
        <input type="number" id="ai-interval" value="1" min="1" max="60">
        <button id="btn-set-interval">Set Interval</button>
    </div>
    <div class="control-row">
        <button id="btn-trigger-ai">Trigger AI Now</button>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Load scheduler status
    fetch('/api/ai/scheduler/status')
        .then(r => r.json())
        .then(data => {
            document.getElementById('ai-scheduler-enabled').checked = data.enabled;
            document.getElementById('ai-interval').value = data.interval_minutes;
        });
    
    // Toggle scheduler
    document.getElementById('ai-scheduler-enabled').addEventListener('change', function() {
        const endpoint = this.checked ? '/api/ai/scheduler/enable' : '/api/ai/scheduler/disable';
        fetch(endpoint, { method: 'POST' });
    });
    
    // Set interval
    document.getElementById('btn-set-interval').addEventListener('click', function() {
        const minutes = document.getElementById('ai-interval').value;
        fetch('/api/ai/scheduler/interval?minutes=' + minutes, { method: 'POST' });
    });
    
    // Trigger now
    document.getElementById('btn-trigger-ai').addEventListener('click', function() {
        fetch('/api/ai/scheduler/trigger', { method: 'POST' })
            .then(r => r.json())
            .then(data => alert('AI moves triggered!'));
    });
});
</script>
```

### Step 6: Restore AI state after restart
The scheduler will automatically restore AI state on first run:
```python
async def run_ai_moves():
    # This already happens:
    # 1. Load all events
    # 2. Build game state from events
    # 3. AI players are restored from database
    # 4. Execute moves
    
    # The key is: on server restart, the scheduler starts
    # and loads AI players from database via get_all_players
```

## Files to Modify
1. `app/main.py` - Add scheduler startup/shutdown
2. `app/api/routes.py` - Add scheduler control endpoints
3. `app/templates/admin.html` - Add UI controls

## Files to Create
1. `app/services/ai_scheduler.py`

## Configuration Options
```python
# In app/config.py
class Settings(BaseSettings):
    ai_scheduler_enabled: bool = True
    ai_scheduler_interval_minutes: int = 1
```

## Testing
1. Enable scheduler in admin panel
2. Wait for interval to pass
3. Verify AI moves execute automatically
4. Disable and verify no automatic moves
5. Restart server and verify AI still works
6. Test with multiple AI players
