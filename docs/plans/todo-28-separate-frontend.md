# Plan: Separate Front-end from Back-end Cleanly

## Overview
Refactor the codebase to cleanly separate the Telegram front-end from the game logic back-end. This involves creating clear interfaces and moving Telegram-specific code to its own package.

## References
- Original TODO: docs/TODO.md item 28

## Current State
- Telegram handlers directly import from `app.game`, `app.events`
- Chat ID association is in the Player table (tightly coupled)
- No clear boundaries between frontend and backend

## Architecture After Refactoring

```
app/
├── core/                    # Domain interfaces
│   ├── interfaces.py        # Protocol definitions
│   ├── events.py           # Event types
│   └── models.py           # Domain models
├── backend/                # Game engine
│   ├── game/
│   │   ├── state.py
│   │   ├── ships.py
│   │   └── renderers/
│   ├── events/
│   │   ├── factory.py
│   │   ├── models.py
│   │   └── saver.py
│   └── services/
│       ├── ai_player.py
│       └── ship_placement.py
├── frontend/              # Telegram, Web, etc.
│   ├── telegram/
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   └── helpers.py
│   └── web/
│       ├── routes.py
│       └── templates/
└── main.py
```

## Implementation Plan

### Step 1: Define core interfaces
Create `app/core/interfaces.py`:
```python
from typing import Protocol, Optional
from app.game.state import GameState
from app.events.models import GameEvent

class GameBackend(Protocol):
    """Protocol defining the game backend interface."""
    
    async def get_state(self) -> GameState:
        """Get current game state."""
        ...
    
    async def apply_event(self, event: GameEvent) -> GameState:
        """Apply an event and return new state."""
        ...
    
    async def can_start_game(self) -> bool:
        """Check if game can be started."""
        ...

class PlayerStore(Protocol):
    """Protocol for player management."""
    
    async def register_player(self, chat_id: int, name: str, color: str) -> None:
        ...
    
    async def get_player_by_chat(self, chat_id: int) -> Optional[dict]:
        ...

class NotificationService(Protocol):
    """Protocol for sending notifications."""
    
    async def send_message(self, chat_id: int, message: str) -> None:
        ...
```

### Step 2: Move Telegram-specific code to frontend package
Create `app/frontend/__init__.py`:
```python
# Frontend package
```

Create `app/frontend/telegram/__init__.py`:
```python
# Telegram frontend
```

### Step 3: Refactor handlers to use interfaces
Modify `app/frontend/telegram/handlers.py`:
```python
from app.core.interfaces import GameBackend, PlayerStore, NotificationService

class TelegramFrontend:
    def __init__(
        self, 
        game_backend: GameBackend,
        player_store: PlayerStore,
        notifications: NotificationService
    ):
        self.game = game_backend
        self.players = player_store
        self.notifications = notifications
    
    async def handle_join(self, chat_id: int, team_name: str) -> str:
        # Use interfaces instead of direct imports
        player = await self.players.get_player_by_chat(chat_id)
        # ...
```

### Step 4: Create concrete implementations
Create `app/backend/postgres_player_store.py`:
```python
from app.core.interfaces import PlayerStore
from app.database import Player, Role, async_session_maker
from sqlalchemy import select

class PostgresPlayerStore(PlayerStore):
    async def register_player(self, chat name: str,_id: int, color: str) -> None:
        async with async_session_maker() as session:
            # Create player record
            ...
    
    async def get_player_by_chat(self, chat_id: int) -> Optional[dict]:
        # Query player by chat_id
        ...
```

### Step 5: Keep chat_id in separate table (optional)
Create `app/database_telegram.py`:
```python
class TelegramPlayer(Base):
    __tablename__ = "telegram_players"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    telegram_username = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
```

This allows the Telegram frontend to be completely separate while still linking to game players.

### Step 6: Update main.py to wire everything
```python
from app.frontend.telegram.handlers import TelegramFrontend
from app.backend.postgres_player_store import PostgresPlayerStore
from app.backend.game_backend import GameBackendImpl
from app.backend.telegram_notifier import TelegramNotifier

# Wire up dependencies
player_store = PostgresPlayerStore()
game_backend = GameBackendImpl()
notifier = TelegramNotifier(bot)

telegram_frontend = TelegramFrontend(
    game_backend=game_backend,
    player_store=player_store,
    notifications=notifier
)
```

## Files to Modify
1. `app/main.py` - Update to use new structure
2. `app/bot/handlers.py` - Refactor to use interfaces

## Files to Create
1. `app/core/__init__.py`
2. `app/core/interfaces.py`
3. `app/frontend/__init__.py`
4. `app/frontend/telegram/__init__.py`
5. `app/backend/__init__.py`
6. `app/backend/game_backend.py`
7. `app/backend/postgres_player_store.py`

## Benefits
- Clear separation of concerns
- Easy to add new frontends (WhatsApp, Discord, etc.)
- Testable with mock implementations
- Game logic reusable across platforms

## Testing
1. Write unit tests for game backend (mock frontend)
2. Write integration tests for Telegram handler (mock backend)
3. Verify all existing functionality works
