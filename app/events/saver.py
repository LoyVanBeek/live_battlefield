from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import GameEvent
from app.events.models import (
    TeamJoinedEvent,
    ShipPlacedEvent,
    ShipRemovedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
    BombsAddedEvent,
    TeamResetEvent,
)


async def save_event(
    db: AsyncSession,
    event: Union[
        TeamJoinedEvent,
        ShipPlacedEvent,
        ShipRemovedEvent,
        BombThrownEvent,
        CodeRedeemedEvent,
        LocationAddedEvent,
        BombsAddedEvent,
        TeamResetEvent,
    ],
) -> GameEvent:
    game_event = event.to_game_event()
    db.add(game_event)
    await db.commit()
    await db.refresh(game_event)
    return game_event
