# Plan: Multiple Games with GameId

## Overview
Add support for multiple simultaneous games by associating each event with a `game_id`. This allows the same instance to host multiple independent games.

## References
- Original TODO: docs/TODO.md item 31

## Current State
- Single game per instance
- All events share the same game context
- No game_id field in database

## Implementation Plan

### Step 1: Add game_id to database schema
Create migration:
```bash
alembic revision --autogenerate -m "add_game_id"
```

Modify the migration to add game_id columns:
```python
# In migration file
op.add_column('game_events', sa.Column('game_id', sa.String(50), nullable=False, server_default='default'))
op.add_column('game_settings', sa.Column('game_id', sa.String(50), nullable=False, server_default='default'))
op.add_column('players', sa.Column('game_id', sa.String(50), nullable=False, server_default='default'))
```

### Step 2: Update database models
Modify `app/database.py`:
```python
class GameEvent(Base):
    __tablename__ = "game_events"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String(50), nullable=False, default="default", index=True)
    event_type = Column(Enum(EventType), nullable=False)
    payload = Column(JSON, nullable=False)
    player_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class GameSettings(Base):
    __tablename__ = "game_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String(50), nullable=False, unique=True, index=True)
    status = Column(Enum(GameStatus), nullable=False, default=GameStatus.WAITING)
    total_locations_needed = Column(Integer, nullable=False, default=33)
    started_at = Column(DateTime, nullable=True)

class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String(50), nullable=False, default="default", index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), nullable=False)
    chat_id = Column(Integer, nullable=True)
    role = Column(Enum(Role), nullable=False, default=Role.TEAM)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Unique constraint per game
    __table_args__ = (
        UniqueConstraint('game_id', 'color', name='uq_player_game_color'),
    )
```

### Step 3: Update GameState to support game_id
Modify `app/game/state.py`:
```python
@dataclass
class GameState:
    game_id: str = "default"
    teams: dict[str, TeamState] = field(default_factory=dict)
    location_codes: dict[int, str] = field(default_factory=dict)
    location_counter: int = 0
    status: GameStatusField = GameStatusField.PREPARING
    
    @classmethod
    def from_events(cls, events: list, game_id: str = "default") -> "GameState":
        state = cls(game_id=game_id)
        # Filter events by game_id
        filtered = [e for e in events if e.game_id == game_id]
        typed_events = create_events(filtered)
        # ... rest of logic
```

### Step 4: Update models.py with game_id queries
Modify `app/models.py`:
```python
async def get_player_by_chat(db: AsyncSession, chat_id: int, game_id: str = "default") -> Optional[Player]:
    result = await db.execute(
        select(Player).where(
            Player.chat_id == chat_id,
            Player.game_id == game_id
        )
    )
    return result.scalar_one_or_none()

async def get_all_teams(db: AsyncSession, game_id: str = "default") -> list[Player]:
    result = await db.execute(
        select(Player).where(
            Player.role == Role.TEAM,
            Player.game_id == game_id
        )
    )
    return list(result.scalars().all())

async def get_game_settings(db: AsyncSession, game_id: str = "default") -> Optional[GameSettings]:
    result = await db.execute(
        select(GameSettings).where(GameSettings.game_id == game_id)
    )
    return result.scalar_one_or_none()

async def get_all_events(db: AsyncSession, game_id: str = "default") -> list[GameEvent]:
    result = await db.execute(
        select(GameEvent)
        .where(GameEvent.game_id == game_id)
        .order_by(GameEvent.created_at)
    )
    return list(result.scalars().all())
```

### Step 5: Update event saving
Modify `app/events/saver.py`:
```python
async def save_event(
    db: AsyncSession,
    game_event: GameEvent,
    player_id: Optional[int] = None,
    game_id: str = "default"
) -> GameEvent:
    # Set game_id on event
    game_event.game_id = game_id
    # ... rest of saving logic
```

### Step 6: Update API routes with game_id
Modify `app/api/routes.py`:
```python
from typing import Optional

DEFAULT_GAME_ID = "default"

@app.get("/api/games")
async def list_games():
    """List all active games."""
    # Query distinct game_ids
    ...

@app.post("/api/games/{game_id}/start")
async def start_game(game_id: str = DEFAULT_GAME_ID):
    """Start a specific game."""
    ...

@app.get("/game/{game_id}")
async def team_page(game_id: str, request: Request, team_color: Optional[str] = None):
    """Team page for a specific game."""
    ...

@app.get("/admin/{game_id}")
async def admin_page(game_id: str, request: Request):
    """Admin page for a specific game."""
    ...
```

### Step 7: Update Telegram handlers to support game_id
Modify `app/bot/handlers.py`:
```python
async def handle_join(
    db, 
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    team_name: str,
    game_id: str = "default"
):
    # Use game_id in all queries
    existing_player = await get_player_by_chat(db, chat_id, game_id)
    events = await get_all_events(db, game_id)
    ...
```

### Step 8: Add game management commands
Telegram commands to manage multiple games:
```
/newgame <game_id> - Create new game
/games - List all games
/switch <game_id> - Switch to different game
```

### Step 9: Update admin UI
Modify templates to show game selector:
```html
<select id="game-selector">
    <option value="default" selected>Default Game</option>
    <option value="tournament">Tournament</option>
</select>
```

## Files to Modify
1. `app/database.py` - Add game_id columns
2. `app/models.py` - Update queries with game_id
3. `app/game/state.py` - Support game_id
4. `app/events/saver.py` - Save game_id on events
5. `app/api/routes.py` - Add game_id to routes
6. `app/bot/handlers.py` - Support game_id
7. `app/templates/admin.html` - Add game selector

## Files to Create
1. Migrations (via alembic)

## Backward Compatibility
- Default game_id = "default"
- All existing queries work with default game_id
- Existing code continues to work without changes

## Testing
1. Create two games with different game_ids
2. Join teams to each game independently
3. Verify events are isolated per game
4. Verify admin can manage each game separately
