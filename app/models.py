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
from sqlalchemy import select, delete, func, or_
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
            import secrets
            token = secrets.token_urlsafe(24)
        admin = Admin(token=token)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
    return admin


async def create_game(db: AsyncSession, name: str | None, gm_token: str, invite_token: str) -> Game:
    game = Game(name=name, gm_token=gm_token, invite_token=invite_token)
    db.add(game)
    await db.commit()
    await db.refresh(game)
    return game


async def get_game_by_invite_token(db: AsyncSession, invite_token: str) -> Optional[Game]:
    result = await db.execute(select(Game).where(Game.invite_token == invite_token))
    return result.scalar_one_or_none()


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


async def delete_game(db: AsyncSession, game_id: uuid.UUID) -> bool:
    await delete_all_players(db, game_id)
    await delete_all_events(db, game_id)
    await delete_all_locations(db, game_id)
    await delete_all_team_tokens(db, game_id)
    game = await get_game(db, game_id)
    if not game:
        return False
    await db.delete(game)
    await db.commit()
    return True


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


async def update_trickle_settings(
    db: AsyncSession, game_id: uuid.UUID, enabled: bool, bombs_per_interval: int, interval_minutes: int, max_bombs: int = 100
) -> Optional[Game]:
    game = await get_game(db, game_id)
    if not game:
        return None
    game.trickle_enabled = enabled
    game.trickle_bombs_per_interval = bombs_per_interval
    game.trickle_interval_minutes = interval_minutes
    game.max_bombs = max_bombs
    game.last_trickle_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(game)
    return game


async def get_active_trickle_games(db: AsyncSession) -> list[Game]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Game).where(
            Game.trickle_enabled == True,
            Game.status == GameStatus.STARTED,
            or_(Game.paused_until == None, Game.paused_until <= now),
        )
    )
    return list(result.scalars().all())


async def update_game_pause(db: AsyncSession, game_id: uuid.UUID, paused_until: datetime | None) -> Optional[Game]:
    game = await get_game(db, game_id)
    if not game:
        return None
    game.paused_until = paused_until
    await db.commit()
    await db.refresh(game)
    return game


async def update_quiz_settings(
    db: AsyncSession, game_id: uuid.UUID, enabled: bool, total_bombs: int = 100
) -> Optional[Game]:
    game = await get_game(db, game_id)
    if not game:
        return None
    game.quiz_enabled = enabled
    game.quiz_total_bombs = total_bombs
    await db.commit()
    await db.refresh(game)
    return game


async def get_quiz_questions(db: AsyncSession, game_id: uuid.UUID) -> list:
    from app.database import QuizQuestion, QuizAnswer
    from sqlalchemy import select

    questions = await db.execute(
        select(QuizQuestion).where(QuizQuestion.game_id == game_id).order_by(QuizQuestion.order)
    )
    result = []
    for q in questions.scalars().all():
        answers = await db.execute(
            select(QuizAnswer).where(QuizAnswer.question_id == q.id).order_by(QuizAnswer.id)
        )
        result.append({
            "id": q.id,
            "question_text": q.question_text,
            "order": q.order,
            "answers": [
                {"id": a.id, "answer_text": a.answer_text, "bomb_value": a.bomb_value, "is_correct": a.is_correct}
                for a in answers.scalars().all()
            ],
        })
    return result


async def save_quiz_questions(db: AsyncSession, game_id: uuid.UUID, questions_data: list[dict]) -> list:
    from app.database import QuizQuestion, QuizAnswer
    from sqlalchemy import delete

    # Remove old questions
    old_qs = await db.execute(select(QuizQuestion).where(QuizQuestion.game_id == game_id))
    for q in old_qs.scalars().all():
        await db.execute(delete(QuizAnswer).where(QuizAnswer.question_id == q.id))
        await db.delete(q)
    await db.commit()

    result = []
    for i, qd in enumerate(questions_data):
        q = QuizQuestion(game_id=game_id, question_text=qd.get("question_text", ""), order=i)
        db.add(q)
        await db.flush()
        answers = qd.get("answers", [])
        for ad in answers:
            a = QuizAnswer(
                question_id=q.id,
                answer_text=ad.get("answer_text", ""),
                bomb_value=ad.get("bomb_value", 0),
                is_correct=ad.get("is_correct", False),
            )
            db.add(a)
            await db.flush()
            ad["id"] = a.id
        qd["id"] = q.id
        result.append(qd)
    await db.commit()
    return result


async def is_game_paused(db: AsyncSession, game_id: uuid.UUID) -> tuple[bool, datetime | None]:
    game = await get_game(db, game_id)
    if not game or not game.paused_until:
        return False, None
    now = datetime.now(timezone.utc)
    if game.paused_until <= now:
        return False, None
    return True, game.paused_until
