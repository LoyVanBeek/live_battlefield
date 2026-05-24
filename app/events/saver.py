from typing import Union, Optional
import logging
import uuid
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


async def _get_legacy_game_id(db: AsyncSession) -> uuid.UUID:
    from app.models import get_all_games
    games = await get_all_games(db)
    if games:
        return games[-1].id  # oldest game (legacy)
    return uuid.uuid4()


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
    game_id: Optional[uuid.UUID] = None,
) -> GameEvent:
    if game_id is None:
        game_id = await _get_legacy_game_id(db)
    game_event = event.to_game_event(game_id=game_id)
    db.add(game_event)
    await db.commit()
    await db.refresh(game_event)

    logger.info(
        f"EVENT: player_id={game_event.player_id} event={game_event.event_type.value} payload={game_event.payload}"
    )

    await manager.broadcast("refresh")

    return game_event
