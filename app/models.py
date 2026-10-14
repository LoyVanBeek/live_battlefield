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


async def delete_location_quiz_questions(
    db: AsyncSession, game_id: uuid.UUID, location_number: Optional[int] = None
) -> int:
    """Delete a game's location-quiz questions and their answers.

    Scoped to a single location when location_number is given. Called whenever
    locations are removed: the questions are keyed by (game_id, location_number)
    rather than by a location id, so leaving them behind would let them resurface
    if the number is reused, and the game_id FK would block deleting the game.
    """
    from app.database import LocationQuizQuestion, LocationQuizAnswer
    from sqlalchemy import delete as sa_delete

    filters = [LocationQuizQuestion.game_id == game_id]
    if location_number is not None:
        filters.append(LocationQuizQuestion.location_number == location_number)

    q_ids = (
        await db.execute(select(LocationQuizQuestion.id).where(*filters))
    ).scalars().all()
    if not q_ids:
        return 0

    await db.execute(
        sa_delete(LocationQuizAnswer).where(LocationQuizAnswer.question_id.in_(list(q_ids)))
    )
    await db.execute(
        sa_delete(LocationQuizQuestion).where(LocationQuizQuestion.id.in_(list(q_ids)))
    )
    await db.commit()
    return len(q_ids)


async def delete_all_locations(db: AsyncSession, game_id: uuid.UUID) -> int:
    await delete_location_quiz_questions(db, game_id)
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
        answers_list = [a for a in answers.scalars().all()]
        # A question's bomb_value is the most it can yield = the highest value
        # among its answers (import may put bombs on any answer).
        q_bomb = max((a.bomb_value for a in answers_list), default=0)
        result.append({
            "id": q.id,
            "question_text": q.question_text,
            "order": q.order,
            "bomb_value": q_bomb,
            "source_url": q.source_url,
            "answers": [
                {"id": a.id, "answer_text": a.answer_text, "bomb_value": a.bomb_value, "is_correct": a.is_correct}
                for a in answers_list
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
        q = QuizQuestion(
            game_id=game_id,
            question_text=qd.get("question_text", ""),
            order=i,
            source_url=qd.get("source_url") or None,
        )
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


async def get_location_quiz_questions(
    db: AsyncSession, game_id: uuid.UUID, location_number: Optional[int] = None
) -> list:
    """Location-scoped quiz questions (with answers), optionally for one location.

    The shape mirrors get_quiz_questions so the shared editor and the team page
    can render both kinds of quiz the same way.
    """
    from app.database import LocationQuizQuestion, LocationQuizAnswer

    query = select(LocationQuizQuestion).where(LocationQuizQuestion.game_id == game_id)
    if location_number is not None:
        query = query.where(LocationQuizQuestion.location_number == location_number)
    query = query.order_by(LocationQuizQuestion.location_number, LocationQuizQuestion.order)

    questions = (await db.execute(query)).scalars().all()
    result = []
    for q in questions:
        answers = (
            await db.execute(
                select(LocationQuizAnswer)
                .where(LocationQuizAnswer.question_id == q.id)
                .order_by(LocationQuizAnswer.id)
            )
        ).scalars().all()
        answers_list = list(answers)
        result.append({
            "id": q.id,
            "location_number": q.location_number,
            "question_text": q.question_text,
            "order": q.order,
            "bomb_value": max((a.bomb_value for a in answers_list), default=0),
            "source_url": q.source_url,
            "answers": [
                {"id": a.id, "answer_text": a.answer_text, "bomb_value": a.bomb_value, "is_correct": a.is_correct}
                for a in answers_list
            ],
        })
    return result


async def get_location_quiz_question_counts(db: AsyncSession, game_id: uuid.UUID) -> dict[int, int]:
    """Map location_number -> number of quiz questions, for the GM overview."""
    from app.database import LocationQuizQuestion

    rows = (
        await db.execute(
            select(LocationQuizQuestion.location_number, func.count(LocationQuizQuestion.id))
            .where(LocationQuizQuestion.game_id == game_id)
            .group_by(LocationQuizQuestion.location_number)
        )
    ).all()
    return {number: count for number, count in rows}


async def save_location_quiz_questions(
    db: AsyncSession, game_id: uuid.UUID, location_number: int, questions_data: list[dict]
) -> list:
    """Replace the quiz questions for one location with the supplied set."""
    from app.database import LocationQuizQuestion, LocationQuizAnswer
    from sqlalchemy import delete

    # Ordered bulk deletes: these tables have no ORM relationships, so the unit
    # of work can't order parent/child deletes and would hit an FK violation.
    old_ids = (
        await db.execute(
            select(LocationQuizQuestion.id).where(
                LocationQuizQuestion.game_id == game_id,
                LocationQuizQuestion.location_number == location_number,
            )
        )
    ).scalars().all()
    if old_ids:
        await db.execute(delete(LocationQuizAnswer).where(LocationQuizAnswer.question_id.in_(list(old_ids))))
        await db.execute(delete(LocationQuizQuestion).where(LocationQuizQuestion.id.in_(list(old_ids))))
        await db.commit()

    result = []
    for i, qd in enumerate(questions_data):
        q = LocationQuizQuestion(
            game_id=game_id,
            location_number=location_number,
            question_text=qd.get("question_text", ""),
            order=i,
            source_url=qd.get("source_url") or None,
        )
        db.add(q)
        await db.flush()
        for ad in qd.get("answers", []):
            a = LocationQuizAnswer(
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


async def set_location_quiz_mode(
    db: AsyncSession, game_id: uuid.UUID, location_number: int, mode: str
) -> Optional[Location]:
    location = await get_location_by_number(db, game_id, location_number)
    if not location:
        return None
    location.quiz_mode = mode
    await db.commit()
    await db.refresh(location)
    return location


async def list_quiz_templates(db: AsyncSession) -> list:
    """Named reusable quizzes as summaries (id, name, counts, derived total)."""
    from app.database import QuizTemplate, QuizTemplateQuestion, QuizTemplateAnswer

    templates = (await db.execute(
        select(QuizTemplate).order_by(QuizTemplate.name)
    )).scalars().all()
    result = []
    for t in templates:
        questions = (await db.execute(
            select(QuizTemplateQuestion).where(QuizTemplateQuestion.template_id == t.id)
        )).scalars().all()
        total = 0
        for q in questions:
            answers = (await db.execute(
                select(QuizTemplateAnswer).where(QuizTemplateAnswer.question_id == q.id)
            )).scalars().all()
            total += max((a.bomb_value for a in answers), default=0)
        result.append({
            "id": t.id,
            "name": t.name,
            "question_count": len(questions),
            "total_bombs": total,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        })
    return result


async def get_quiz_template(db: AsyncSession, template_id: int) -> Optional[dict]:
    """Full template in the same shape as get_quiz_questions (editor-ready)."""
    from app.database import QuizTemplate, QuizTemplateQuestion, QuizTemplateAnswer

    template = (await db.execute(
        select(QuizTemplate).where(QuizTemplate.id == template_id)
    )).scalar_one_or_none()
    if not template:
        return None
    questions = (await db.execute(
        select(QuizTemplateQuestion)
        .where(QuizTemplateQuestion.template_id == template.id)
        .order_by(QuizTemplateQuestion.order)
    )).scalars().all()
    q_list = []
    for q in questions:
        answers = (await db.execute(
            select(QuizTemplateAnswer)
            .where(QuizTemplateAnswer.question_id == q.id)
            .order_by(QuizTemplateAnswer.id)
        )).scalars().all()
        answers_list = [a for a in answers]
        q_list.append({
            "id": q.id,
            "question_text": q.question_text,
            "order": q.order,
            "bomb_value": max((a.bomb_value for a in answers_list), default=0),
            "source_url": q.source_url,
            "answers": [
                {"id": a.id, "answer_text": a.answer_text, "bomb_value": a.bomb_value, "is_correct": a.is_correct}
                for a in answers_list
            ],
        })
    return {"id": template.id, "name": template.name, "questions": q_list}


async def delete_quiz_template(db: AsyncSession, template_id: int) -> bool:
    from app.database import QuizTemplate, QuizTemplateQuestion, QuizTemplateAnswer
    from sqlalchemy import delete

    template = (await db.execute(
        select(QuizTemplate).where(QuizTemplate.id == template_id)
    )).scalar_one_or_none()
    if not template:
        return False
    # Bulk deletes run in this exact order (there are no ORM relationships to
    # infer parent/child ordering, so the unit of work cannot be trusted here).
    question_ids = (await db.execute(
        select(QuizTemplateQuestion.id).where(QuizTemplateQuestion.template_id == template.id)
    )).scalars().all()
    if question_ids:
        await db.execute(delete(QuizTemplateAnswer).where(QuizTemplateAnswer.question_id.in_(question_ids)))
        await db.execute(delete(QuizTemplateQuestion).where(QuizTemplateQuestion.template_id == template.id))
    await db.execute(delete(QuizTemplate).where(QuizTemplate.id == template.id))
    await db.commit()
    return True


async def save_quiz_template(
    db: AsyncSession, name: str, questions_data: list[dict], template_id: Optional[int] = None
) -> Optional[dict]:
    """Create or overwrite a reusable quiz. The name is the identity: saving under
    an existing name replaces that template (overwrite-by-name). When template_id is
    given the template is updated in place (allowing a rename)."""
    from app.database import QuizTemplate, QuizTemplateQuestion, QuizTemplateAnswer
    from sqlalchemy import delete

    existing = (await db.execute(
        select(QuizTemplate).where(QuizTemplate.name == name)
    )).scalar_one_or_none()
    if existing and (template_id is None or existing.id != template_id):
        if not await delete_quiz_template(db, existing.id):
            return None

    if template_id is not None:
        template = (await db.execute(
            select(QuizTemplate).where(QuizTemplate.id == template_id)
        )).scalar_one_or_none()
        if not template:
            return None
        template.name = name
        template.updated_at = datetime.now(timezone.utc)
        old_ids = (await db.execute(
            select(QuizTemplateQuestion.id).where(QuizTemplateQuestion.template_id == template.id)
        )).scalars().all()
        if old_ids:
            await db.execute(delete(QuizTemplateAnswer).where(QuizTemplateAnswer.question_id.in_(old_ids)))
            await db.execute(delete(QuizTemplateQuestion).where(QuizTemplateQuestion.template_id == template.id))
        await db.flush()
    else:
        template = QuizTemplate(name=name)
        db.add(template)
        await db.flush()

    for i, qd in enumerate(questions_data):
        q = QuizTemplateQuestion(
            template_id=template.id,
            question_text=qd.get("question_text", ""),
            order=i,
            source_url=qd.get("source_url") or None,
        )
        db.add(q)
        await db.flush()
        for ad in qd.get("answers", []):
            db.add(QuizTemplateAnswer(
                question_id=q.id,
                answer_text=ad.get("answer_text", ""),
                bomb_value=ad.get("bomb_value", 0),
                is_correct=ad.get("is_correct", False),
            ))
    await db.commit()
    return await get_quiz_template(db, template.id)


# --- Location-quiz library (reusable location quizzes) ---


async def list_location_quiz_templates(db: AsyncSession) -> list:
    """Named reusable location quizzes as summaries (id, name, counts, total)."""
    from app.database import (
        LocationQuizTemplate,
        LocationQuizTemplateQuestion,
        LocationQuizTemplateAnswer,
    )

    templates = (await db.execute(
        select(LocationQuizTemplate).order_by(LocationQuizTemplate.name)
    )).scalars().all()
    result = []
    for t in templates:
        questions = (await db.execute(
            select(LocationQuizTemplateQuestion).where(LocationQuizTemplateQuestion.template_id == t.id)
        )).scalars().all()
        total = 0
        for q in questions:
            answers = (await db.execute(
                select(LocationQuizTemplateAnswer).where(LocationQuizTemplateAnswer.question_id == q.id)
            )).scalars().all()
            total += max((a.bomb_value for a in answers), default=0)
        result.append({
            "id": t.id,
            "name": t.name,
            "question_count": len(questions),
            "total_bombs": total,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        })
    return result


async def get_location_quiz_template(db: AsyncSession, template_id: int) -> Optional[dict]:
    """Full template in the same shape as get_location_quiz_questions (editor-ready)."""
    from app.database import (
        LocationQuizTemplate,
        LocationQuizTemplateQuestion,
        LocationQuizTemplateAnswer,
    )

    template = (await db.execute(
        select(LocationQuizTemplate).where(LocationQuizTemplate.id == template_id)
    )).scalar_one_or_none()
    if not template:
        return None
    questions = (await db.execute(
        select(LocationQuizTemplateQuestion)
        .where(LocationQuizTemplateQuestion.template_id == template.id)
        .order_by(LocationQuizTemplateQuestion.order)
    )).scalars().all()
    q_list = []
    for q in questions:
        answers = (await db.execute(
            select(LocationQuizTemplateAnswer)
            .where(LocationQuizTemplateAnswer.question_id == q.id)
            .order_by(LocationQuizTemplateAnswer.id)
        )).scalars().all()
        answers_list = list(answers)
        q_list.append({
            "id": q.id,
            "question_text": q.question_text,
            "order": q.order,
            "bomb_value": max((a.bomb_value for a in answers_list), default=0),
            "source_url": q.source_url,
            "answers": [
                {"id": a.id, "answer_text": a.answer_text, "bomb_value": a.bomb_value, "is_correct": a.is_correct}
                for a in answers_list
            ],
        })
    return {"id": template.id, "name": template.name, "questions": q_list}


async def delete_location_quiz_template(db: AsyncSession, template_id: int) -> bool:
    from app.database import (
        LocationQuizTemplate,
        LocationQuizTemplateQuestion,
        LocationQuizTemplateAnswer,
    )

    template = (await db.execute(
        select(LocationQuizTemplate).where(LocationQuizTemplate.id == template_id)
    )).scalar_one_or_none()
    if not template:
        return False
    # Ordered bulk deletes: no ORM relationships to infer parent/child ordering.
    question_ids = (await db.execute(
        select(LocationQuizTemplateQuestion.id).where(LocationQuizTemplateQuestion.template_id == template.id)
    )).scalars().all()
    if question_ids:
        await db.execute(delete(LocationQuizTemplateAnswer).where(LocationQuizTemplateAnswer.question_id.in_(list(question_ids))))
        await db.execute(delete(LocationQuizTemplateQuestion).where(LocationQuizTemplateQuestion.template_id == template.id))
    await db.execute(delete(LocationQuizTemplate).where(LocationQuizTemplate.id == template.id))
    await db.commit()
    return True


async def save_location_quiz_template(
    db: AsyncSession, name: str, questions_data: list[dict], template_id: Optional[int] = None
) -> Optional[dict]:
    """Create or overwrite a reusable location quiz (overwrite-by-name).

    Mirrors save_quiz_template: the name is the identity, and passing template_id
    updates in place (allowing a rename).
    """
    from app.database import (
        LocationQuizTemplate,
        LocationQuizTemplateQuestion,
        LocationQuizTemplateAnswer,
    )

    existing = (await db.execute(
        select(LocationQuizTemplate).where(LocationQuizTemplate.name == name)
    )).scalar_one_or_none()
    if existing and (template_id is None or existing.id != template_id):
        if not await delete_location_quiz_template(db, existing.id):
            return None

    if template_id is not None:
        template = (await db.execute(
            select(LocationQuizTemplate).where(LocationQuizTemplate.id == template_id)
        )).scalar_one_or_none()
        if not template:
            return None
        template.name = name
        template.updated_at = datetime.now(timezone.utc)
        old_ids = (await db.execute(
            select(LocationQuizTemplateQuestion.id).where(LocationQuizTemplateQuestion.template_id == template.id)
        )).scalars().all()
        if old_ids:
            await db.execute(delete(LocationQuizTemplateAnswer).where(LocationQuizTemplateAnswer.question_id.in_(list(old_ids))))
            await db.execute(delete(LocationQuizTemplateQuestion).where(LocationQuizTemplateQuestion.template_id == template.id))
        await db.flush()
    else:
        template = LocationQuizTemplate(name=name)
        db.add(template)
        await db.flush()

    for i, qd in enumerate(questions_data):
        q = LocationQuizTemplateQuestion(
            template_id=template.id,
            question_text=qd.get("question_text", ""),
            order=i,
            source_url=qd.get("source_url") or None,
        )
        db.add(q)
        await db.flush()
        for ad in qd.get("answers", []):
            db.add(LocationQuizTemplateAnswer(
                question_id=q.id,
                answer_text=ad.get("answer_text", ""),
                bomb_value=ad.get("bomb_value", 0),
                is_correct=ad.get("is_correct", False),
            ))
    await db.commit()
    return await get_location_quiz_template(db, template.id)


# --- Location sets (reusable location layouts) ---


async def list_location_sets(db: AsyncSession) -> list:
    """Named reusable layouts as summaries (id, name, counts, updated)."""
    from app.database import LocationSet, LocationSetLocation

    sets = (await db.execute(
        select(LocationSet).order_by(LocationSet.name)
    )).scalars().all()
    result = []
    for s in sets:
        locations = (await db.execute(
            select(LocationSetLocation).where(LocationSetLocation.set_id == s.id)
        )).scalars().all()
        result.append({
            "id": s.id,
            "name": s.name,
            "location_count": len(locations),
            "quiz_count": sum(1 for loc in locations if loc.quiz_json),
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })
    return result


async def get_location_set(db: AsyncSession, set_id: int) -> Optional[dict]:
    """Full set: every saved location (with its parsed quiz) in number order."""
    from app.database import LocationSet, LocationSetLocation
    import json as _json

    loc_set = (await db.execute(
        select(LocationSet).where(LocationSet.id == set_id)
    )).scalar_one_or_none()
    if not loc_set:
        return None
    locations = (await db.execute(
        select(LocationSetLocation)
        .where(LocationSetLocation.set_id == loc_set.id)
        .order_by(LocationSetLocation.number, LocationSetLocation.id)
    )).scalars().all()
    entries = []
    for loc in locations:
        questions: list = []
        if loc.quiz_json:
            try:
                questions = _json.loads(loc.quiz_json)
            except (ValueError, TypeError):
                questions = []
        entries.append({
            "id": loc.id,
            "number": loc.number,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "code": loc.code,
            "bomb_value": loc.bomb_value,
            "quiz_mode": loc.quiz_mode,
            "questions": questions,
        })
    return {"id": loc_set.id, "name": loc_set.name, "locations": entries}


async def delete_location_set(db: AsyncSession, set_id: int) -> bool:
    from app.database import LocationSet, LocationSetLocation

    loc_set = (await db.execute(
        select(LocationSet).where(LocationSet.id == set_id)
    )).scalar_one_or_none()
    if not loc_set:
        return False
    await db.execute(delete(LocationSetLocation).where(LocationSetLocation.set_id == loc_set.id))
    await db.execute(delete(LocationSet).where(LocationSet.id == loc_set.id))
    await db.commit()
    return True


async def save_locations_as_set(db: AsyncSession, game_id: uuid.UUID, name: str) -> Optional[dict]:
    """Snapshot a game's current locations (with quizzes) into a named set.

    Overwrite-by-name, mirroring the quiz library. Codes are captured verbatim so
    a re-applied layout keeps its printed number -> code mapping.
    """
    from app.database import LocationSet, LocationSetLocation
    import json as _json

    locations = await get_game_locations(db, game_id)
    if not locations:
        return None
    # Capture primitives before any commit expires these rows.
    rows = [
        (loc.number, loc.latitude, loc.longitude, loc.code, loc.bomb_value, loc.quiz_mode)
        for loc in locations
    ]

    existing = (await db.execute(
        select(LocationSet).where(LocationSet.name == name)
    )).scalar_one_or_none()
    if existing:
        await delete_location_set(db, existing.id)

    loc_set = LocationSet(name=name)
    db.add(loc_set)
    await db.flush()

    for number, latitude, longitude, code, bomb_value, quiz_mode in rows:
        questions = await get_location_quiz_questions(db, game_id, number)
        # Strip row ids: applying a set always creates fresh question/answer rows.
        for q in questions:
            q.pop("id", None)
            q.pop("location_number", None)
            for a in q.get("answers", []):
                a.pop("id", None)
        db.add(LocationSetLocation(
            set_id=loc_set.id,
            number=number,
            latitude=latitude,
            longitude=longitude,
            code=code,
            bomb_value=bomb_value,
            quiz_mode=quiz_mode,
            quiz_json=_json.dumps(questions) if questions else None,
        ))
    await db.commit()
    return await get_location_set(db, loc_set.id)


async def apply_location_set(db: AsyncSession, game_id: uuid.UUID, set_id: int) -> Optional[dict]:
    """Replace a game's locations with a saved set.

    Restores numbers, coordinates, codes, bomb values, modes and quizzes 1:1.
    Existing locations (and their quizzes) are removed first, with removal events,
    so the saved codes stay unique and event-derived location state stays correct.
    """
    from app.database import Location
    from app.events.models import LocationAddedEvent, LocationRemovedEvent
    from app.events.saver import save_event

    loc_set = await get_location_set(db, set_id)
    if not loc_set:
        return None

    current = await get_game_locations(db, game_id)
    if current:
        removed = [(loc.number, loc.bomb_value) for loc in current]
        await delete_all_locations(db, game_id)
        for number, bomb_value in removed:
            await save_event(
                db,
                LocationRemovedEvent(number=number, bomb_value=bomb_value),
                game_id,
            )

    created = []
    for entry in loc_set["locations"]:
        number = entry["number"]
        db.add(Location(
            game_id=game_id,
            number=number,
            latitude=entry["latitude"],
            longitude=entry["longitude"],
            code=entry["code"],
            bomb_value=entry["bomb_value"],
            quiz_mode=entry["quiz_mode"],
        ))
        await save_event(
            db,
            LocationAddedEvent(
                number=number,
                latitude=entry["latitude"],
                longitude=entry["longitude"],
                code=entry["code"],
                bomb_value=entry["bomb_value"],
            ),
            game_id,
        )
        questions = entry.get("questions") or []
        if questions:
            await save_location_quiz_questions(db, game_id, number, questions)
        created.append({"number": number, "code": entry["code"]})

    await db.commit()
    return {"id": loc_set["id"], "name": loc_set["name"], "locations": created}


async def is_game_paused(db: AsyncSession, game_id: uuid.UUID) -> tuple[bool, datetime | None]:
    game = await get_game(db, game_id)
    if not game or not game.paused_until:
        return False, None
    now = datetime.now(timezone.utc)
    if game.paused_until <= now:
        return False, None
    return True, game.paused_until
