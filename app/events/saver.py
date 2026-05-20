from typing import Union
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import GameEvent
from app.sse_manager import manager
from app.events.models import (
    TeamJoinedEvent,
    ShipPlacedEvent,
    ShipRemovedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
    LocationRemovedEvent,
    BombsAddedEvent,
    TeamResetEvent,
    GameStartedEvent,
    GameEndedEvent,
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
        LocationRemovedEvent,
        BombsAddedEvent,
        TeamResetEvent,
        GameStartedEvent,
        GameEndedEvent,
    ],
) -> GameEvent:
    game_event = event.to_game_event()
    db.add(game_event)
    await db.commit()
    await db.refresh(game_event)

    logger.info(
        f"EVENT: player_id={game_event.player_id} event={game_event.event_type.value} payload={game_event.payload}"
    )

    await manager.broadcast("refresh")

    return game_event
