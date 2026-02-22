from app.database import (
    Base,
    Player,
    GameEvent,
    Location,
    EventType,
    Role,
    GameSettings,
    GameStatus,
)
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime


async def get_player_by_chat(db: AsyncSession, chat_id: int) -> Optional[Player]:
    result = await db.execute(select(Player).where(Player.chat_id == chat_id))
    return result.scalar_one_or_none()


async def get_player_by_id(db: AsyncSession, player_id: int) -> Optional[Player]:
    result = await db.execute(select(Player).where(Player.id == player_id))
    return result.scalar_one_or_none()


async def get_player_by_color(db: AsyncSession, color: str) -> Optional[Player]:
    result = await db.execute(
        select(Player).where(Player.color == color, Player.role == Role.TEAM)
    )
    return result.scalar_one_or_none()


async def create_player(
    db: AsyncSession, name: str, color: str, chat_id: int, role: Role = Role.TEAM
) -> Player:
    player = Player(name=name, color=color, chat_id=chat_id, role=role)
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def get_all_teams(db: AsyncSession) -> list[Player]:
    result = await db.execute(select(Player).where(Player.role == Role.TEAM))
    return list(result.scalars().all())


async def get_all_game_masters(db: AsyncSession) -> list[Player]:
    result = await db.execute(select(Player).where(Player.role == Role.GAMEMASTER))
    return list(result.scalars().all())


async def add_event(
    db: AsyncSession,
    event_type: EventType,
    payload: dict,
    player_id: Optional[int] = None,
) -> GameEvent:
    event = GameEvent(event_type=event_type, payload=payload, player_id=player_id)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_all_events(db: AsyncSession) -> list[GameEvent]:
    result = await db.execute(select(GameEvent).order_by(GameEvent.created_at))
    return list(result.scalars().all())


async def get_location_by_number(db: AsyncSession, number: int) -> Optional[Location]:
    result = await db.execute(select(Location).where(Location.number == number))
    return result.scalar_one_or_none()


async def get_next_location_number(db: AsyncSession) -> int:
    result = await db.execute(
        select(Location).order_by(Location.number.desc()).limit(1)
    )
    last_location = result.scalar_one_or_none()
    if last_location:
        return last_location.number + 1
    return 1


async def create_location(
    db: AsyncSession, number: int, latitude: float, longitude: float, code: str
) -> Location:
    location = Location(
        number=number, latitude=latitude, longitude=longitude, code=code
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


async def get_all_locations(db: AsyncSession) -> list[Location]:
    result = await db.execute(select(Location).order_by(Location.number))
    return list(result.scalars().all())


async def get_game_settings(db: AsyncSession) -> Optional[GameSettings]:
    result = await db.execute(select(GameSettings).limit(1))
    return result.scalar_one_or_none()


async def get_or_create_game_settings(db: AsyncSession) -> GameSettings:
    settings = await get_game_settings(db)
    if not settings:
        settings = GameSettings(status=GameStatus.WAITING, total_locations_needed=33)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


async def update_game_settings(db: AsyncSession, **kwargs) -> GameSettings:
    settings = await get_or_create_game_settings(db)
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await db.commit()
    await db.refresh(settings)
    return settings


async def delete_all_events(db: AsyncSession) -> int:
    result = await db.execute(select(GameEvent))
    events = result.scalars().all()
    count = len(events)
    for event in events:
        await db.delete(event)
    await db.commit()
    return count


async def delete_all_locations(db: AsyncSession) -> int:
    result = await db.execute(select(Location))
    locations = result.scalars().all()
    count = len(locations)
    for loc in locations:
        await db.delete(loc)
    await db.commit()
    return count


async def delete_all_players(db: AsyncSession) -> int:
    result = await db.execute(select(Player).where(Player.role == Role.TEAM))
    players = result.scalars().all()
    count = len(players)
    for player in players:
        await db.delete(player)
    await db.commit()
    return count


async def reset_game_settings(db: AsyncSession) -> GameSettings:
    settings = await get_or_create_game_settings(db)
    settings.status = GameStatus.WAITING
    settings.total_locations_needed = 33
    settings.started_at = None
    await db.commit()
    await db.refresh(settings)
    return settings
