from app.database import (
    Base,
    Player,
    GameEvent,
    Location,
    EventType,
    Role,
    GameStatus,
    Admin,
    Game,
    TeamToken,
)
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone
import uuid


async def get_player_by_chat(db: AsyncSession, chat_id: int) -> Optional[Player]:
    result = await db.execute(select(Player).where(Player.chat_id == chat_id))
    return result.scalar_one_or_none()


async def get_player_by_id(db: AsyncSession, player_id: int) -> Optional[Player]:
    result = await db.execute(select(Player).where(Player.id == player_id))
    return result.scalar_one_or_none()



async def create_player(
    db: AsyncSession, game_id: uuid.UUID, name: str, color: str, chat_id: int | None, role: Role = Role.TEAM
) -> Player:
    player = Player(game_id=game_id, name=name, color=color, chat_id=chat_id, role=role)
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def get_all_players(db: AsyncSession) -> list[Player]:
    result = await db.execute(select(Player))
    return list(result.scalars().all())


async def get_all_players_in_game(db: AsyncSession, game_id: uuid.UUID) -> list[Player]:
    result = await db.execute(select(Player).where(Player.game_id == game_id))
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



async def get_location_by_number(db: AsyncSession, game_id: uuid.UUID, number: int) -> Optional[Location]:
    result = await db.execute(
        select(Location).where(Location.game_id == game_id, Location.number == number)
    )
    return result.scalar_one_or_none()


async def get_next_location_number(db: AsyncSession, game_id: uuid.UUID) -> int:
    result = await db.execute(
        select(Location)
        .where(Location.game_id == game_id)
        .order_by(Location.number.desc())
        .limit(1)
    )
    last_location = result.scalar_one_or_none()
    if last_location:
        return last_location.number + 1
    return 1


async def create_location(
    db: AsyncSession, game_id: uuid.UUID, number: int, latitude: float, longitude: float, code: str
) -> Location:
    location = Location(
        game_id=game_id, number=number, latitude=latitude, longitude=longitude, code=code
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


async def delete_all_events(db: AsyncSession, game_id: uuid.UUID) -> int:
    result = await db.execute(
        select(GameEvent).where(GameEvent.game_id == game_id)
    )
    events = result.scalars().all()
    count = len(events)
    for event in events:
        await db.delete(event)
    await db.commit()
    return count


async def delete_all_locations(db: AsyncSession, game_id: uuid.UUID) -> int:
    result = await db.execute(
        select(Location).where(Location.game_id == game_id)
    )
    locations = result.scalars().all()
    count = len(locations)
    for loc in locations:
        await db.delete(loc)
    await db.commit()
    return count


async def delete_all_players(db: AsyncSession, game_id: uuid.UUID) -> int:
    result = await db.execute(
        select(Player).where(Player.game_id == game_id)
    )
    players = result.scalars().all()
    count = len(players)
    for player in players:
        await db.delete(player)
    await db.commit()
    return count


# --- Multi-game models ---

async def get_admin(db: AsyncSession) -> Optional[Admin]:
    result = await db.execute(select(Admin).limit(1))
    return result.scalar_one_or_none()


async def get_or_create_admin(db: AsyncSession) -> Admin:
    from app.config import settings as app_settings
    token = app_settings.admin_token or ""
    admin = await get_admin(db)
    if admin:
        if token and admin.token != token:
            admin.token = token
            await db.commit()
            await db.refresh(admin)
    else:
        if not token:
            from app.events.models import generate_team_token
            token = generate_team_token()
        admin = Admin(token=token)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
    return admin


async def create_game(db: AsyncSession, name: str | None, gm_token: str) -> Game:
    game = Game(name=name, gm_token=gm_token)
    db.add(game)
    await db.commit()
    await db.refresh(game)
    return game


async def get_game(db: AsyncSession, game_id: uuid.UUID) -> Optional[Game]:
    result = await db.execute(select(Game).where(Game.id == game_id))
    return result.scalar_one_or_none()


async def get_game_by_gm_token(db: AsyncSession, gm_token: str) -> Optional[Game]:
    result = await db.execute(select(Game).where(Game.gm_token == gm_token))
    return result.scalar_one_or_none()


async def get_all_games(db: AsyncSession) -> list[Game]:
    result = await db.execute(select(Game).order_by(Game.created_at.desc()))
    return list(result.scalars().all())


async def lookup_team_token(db: AsyncSession, token: str) -> Optional[tuple]:
    """Returns (game_id, color) or None."""
    result = await db.execute(select(TeamToken).where(TeamToken.token == token))
    tt = result.scalar_one_or_none()
    if tt:
        return (str(tt.game_id), tt.color)
    return None


async def create_team_token(db: AsyncSession, game_id: uuid.UUID, token: str, color: str) -> TeamToken:
    tt = TeamToken(game_id=game_id, token=token, color=color)
    db.add(tt)
    await db.commit()
    await db.refresh(tt)
    return tt


async def delete_team_token(db: AsyncSession, game_id: uuid.UUID, color: str) -> bool:
    result = await db.execute(
        select(TeamToken).where(TeamToken.game_id == game_id, TeamToken.color == color)
    )
    tt = result.scalar_one_or_none()
    if tt:
        await db.delete(tt)
        await db.commit()
        return True
    return False


async def delete_all_team_tokens(db: AsyncSession, game_id: uuid.UUID) -> int:
    result = await db.execute(
        select(TeamToken).where(TeamToken.game_id == game_id)
    )
    tokens = result.scalars().all()
    count = len(tokens)
    for token in tokens:
        await db.delete(token)
    await db.commit()
    return count


async def get_game_events(db: AsyncSession, game_id: uuid.UUID) -> list[GameEvent]:
    result = await db.execute(
        select(GameEvent)
        .where(GameEvent.game_id == game_id)
        .order_by(GameEvent.created_at)
    )
    return list(result.scalars().all())


async def get_game_locations(db: AsyncSession, game_id: uuid.UUID) -> list[Location]:
    result = await db.execute(
        select(Location)
        .where(Location.game_id == game_id)
        .order_by(Location.number)
    )
    return list(result.scalars().all())


async def get_player_by_color_in_game(db: AsyncSession, game_id: uuid.UUID, color: str) -> Optional[Player]:
    result = await db.execute(
        select(Player).where(
            Player.game_id == game_id,
            Player.color == color,
        )
    )
    return result.scalar_one_or_none()


async def get_all_teams_in_game(db: AsyncSession, game_id: uuid.UUID) -> list[Player]:
    result = await db.execute(
        select(Player)
        .where(Player.game_id == game_id, Player.role == Role.TEAM)
    )
    return list(result.scalars().all())


async def update_game_status(
    db: AsyncSession, game_id: uuid.UUID, status: GameStatus, started_at: Optional[datetime] = None
) -> Optional[Game]:
    game = await get_game(db, game_id)
    if not game:
        return None
    game.status = status
    if started_at:
        game.started_at = started_at
    await db.commit()
    await db.refresh(game)
    return game
