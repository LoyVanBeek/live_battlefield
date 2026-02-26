from typing import Union
import logging
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

logger = logging.getLogger(__name__)


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

    logger.info(f"EVENT: {game_event.event_type.value} - {game_event.payload}")

    return game_event
