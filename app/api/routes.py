from fastapi import FastAPI, Depends, Request, HTTPException, Query
from fastapi.responses import Response, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import logging
import uuid

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pydantic import BaseModel
from typing import Optional, Any, Dict
from app.types import TeamJsonResult, CellData
from app.translations import get_translations, detect_language, SUPPORTED_LANGS
from app.sse_manager import manager
import os
import json
import math
import random
import string
import asyncio

from app.config import settings
from app.game.state import GameState, TEAM_COLORS, TeamState
from app.game.board import (
    render_all_public_boards,
    render_private_board,
    render_board,
    boards_to_bytes,
    create_public_board_gif,
)
from app.game.ships import (
    SHIP_SIZES,
    SHIP_COUNTS,
    VALID_SHIP_TYPES,
    coordinate_to_string,
)
from app.game.state import BombResult, GameState, GameStatusField
from app.events import (
    EventType,
    TeamJoinedEvent,
    ShipPlacedEvent,
    ShipRemovedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
    BombsAddedEvent,
    TeamResetEvent,
    GameStartedEvent,
    GameEndedEvent,
    save_event,
)

try:
    from telegram import Bot

    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False

api_engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
api_session_maker = async_sessionmaker(
    api_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_api_db():
    async with api_session_maker() as session:
        yield session


async def _get_legacy_game_id(db: AsyncSession) -> uuid.UUID:
    from app.models import get_all_games
    games = await get_all_games(db)
    if games:
        return games[-1].id
    return uuid.uuid4()


# --- New auth dependencies ---

async def verify_super_admin(
    token: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_super_admin
    sa = await get_super_admin(db)
    if not sa or sa.token != token:
        raise HTTPException(status_code=404)
    return token


async def verify_gm_token(
    gm_token: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_by_gm_token
    game = await get_game_by_gm_token(db, gm_token)
    if not game:
        raise HTTPException(status_code=404)
    return str(game.id)


async def verify_team_token(
    team_token: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import lookup_team_token
    result = await lookup_team_token(db, team_token)
    if not result:
        raise HTTPException(status_code=404)
    game_id, color = result
    return {"game_id": game_id, "color": color}


async def verify_team_or_gm(
    gm_token: Optional[str] = Query(None),
    team_token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
):
    if gm_token:
        from app.models import get_game_by_gm_token
        game = await get_game_by_gm_token(db, gm_token)
        if game:
            return {"role": "gm", "game_id": str(game.id)}

    if team_token:
        from app.models import lookup_team_token
        result = await lookup_team_token(db, team_token)
        if result:
            game_id, color = result
            return {"role": "team", "game_id": game_id, "color": color, "team_token": team_token}

    raise HTTPException(status_code=404)


# --- Old auth dependencies (backward compat, use new models) ---

async def verify_admin_token(
    admin_token: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_super_admin
    sa = await get_super_admin(db)
    if not sa or sa.token != admin_token:
        raise HTTPException(status_code=404)
    return admin_token


async def verify_team_or_admin_token(
    admin_token: Optional[str] = Query(None),
    team_token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
):
    if admin_token:
        from app.models import get_super_admin
        sa = await get_super_admin(db)
        if sa and sa.token == admin_token:
            return admin_token

    if team_token:
        from app.models import lookup_team_token
        result = await lookup_team_token(db, team_token)
        if result:
            return team_token

    raise HTTPException(status_code=404)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with api_session_maker() as db:
            from app.models import get_super_admin
            sa = await get_super_admin(db)
            if sa:
                logger.info("Super admin panel: /admin/%s", sa.token)
    except Exception:
        logger.warning("Could not check super admin token on startup")
    yield


app = FastAPI(title="Live Battlefield API", lifespan=lifespan)

templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


class ExecuteCommand(BaseModel):
    team_color: str
    command: str
    args: dict[str, Any]


class QuickAction(BaseModel):
    team_color: str
    count: Optional[int] = 1


class AddAIAction(BaseModel):
    team_color: str
    name: Optional[str] = None


class RemoveShipAction(BaseModel):
    team_color: str
    row: int
    col: int


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/map")


@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    return templates.TemplateResponse(request, "map.html", {"request": request})


@app.get("/api/locations")
async def get_public_locations(
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_locations

    locations = await get_game_locations(db, uuid.UUID(game_id))

    return {
        "locations": [
            {
                "number": loc.number,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "bomb_value": loc.bomb_value,
            }
            for loc in locations
        ]
    }


@app.get("/api/public-state")
async def get_public_state(
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events, get_game
    from app.game.state import GameState

    game = await get_game(db, uuid.UUID(game_id))
    events = await get_game_events(db, uuid.UUID(game_id))
    state = GameState.from_events(events)

    teams = []
    for color, team in state.teams.items():
        from app.services.ai_player import get_ai_player

        ai = get_ai_player(game_id, color)
        teams.append(
            {
                "name": team.name,
                "color": team.color,
                "bombs": team.bombs,
                "ships_placed": sum(team.placed_ship_types.values()),
                "ships_remaining": sum(SHIP_COUNTS.values()) - len(team.get_sunk_ships()),
                "ships_sunk": len(team.get_sunk_ships()),
                "is_ai": ai is not None,
            }
        )

    return {
        "status": game.status.value if game else "PREPARING",
        "teams": teams,
    }


@app.get("/admin", response_class=HTMLResponse)
async def super_admin_login(request: Request):
    return templates.TemplateResponse(
        request, "super_admin_login.html", {"request": request}
    )


@app.get("/admin/{super_token}", response_class=HTMLResponse)
async def super_admin_dashboard(
    request: Request, super_token: str, db: AsyncSession = Depends(get_api_db)
):
    from app.models import get_super_admin

    sa = await get_super_admin(db)
    if not sa or sa.token != super_token:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request, "super_admin.html", {"request": request, "token": super_token}
    )


@app.get("/admin/game/{gm_token}", response_class=HTMLResponse)
async def game_master_page(
    request: Request, gm_token: str, db: AsyncSession = Depends(get_api_db)
):
    from app.models import get_game_by_gm_token

    game = await get_game_by_gm_token(db, gm_token)
    if not game:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request, "admin.html", {"request": request, "token": gm_token}
    )


@app.get("/admin/game/{gm_token}/locations-secret", response_class=HTMLResponse)
async def game_master_locations_page(
    request: Request, gm_token: str, db: AsyncSession = Depends(get_api_db)
):
    from app.models import get_game_by_gm_token

    game = await get_game_by_gm_token(db, gm_token)
    if not game:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request, "locations.html", {"request": request, "token": gm_token}
    )


@app.get("/admin/game/{gm_token}/events", response_class=HTMLResponse)
async def game_master_events_page(
    request: Request, gm_token: str, db: AsyncSession = Depends(get_api_db)
):
    from app.models import get_game_by_gm_token

    game = await get_game_by_gm_token(db, gm_token)
    if not game:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request, "events.html", {"request": request, "token": gm_token}
    )


# Keep old /admin/{token} sub-routes for backward compat (now check gm_token)
@app.get("/admin/{token}/locations-secret", response_class=HTMLResponse)
async def admin_locations_page_legacy(
    request: Request, token: str, db: AsyncSession = Depends(get_api_db)
):
    from app.models import get_game_by_gm_token

    game = await get_game_by_gm_token(db, token)
    if not game:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request, "locations.html", {"request": request, "token": token}
    )


@app.get("/admin/{token}/events", response_class=HTMLResponse)
async def admin_events_page_legacy(
    request: Request, token: str, db: AsyncSession = Depends(get_api_db)
):
    from app.models import get_game_by_gm_token

    game = await get_game_by_gm_token(db, token)
    if not game:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request, "events.html", {"request": request, "token": token}
    )


@app.post("/api/admin/create-game")
async def admin_create_game(
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_super_admin),
):
    from app.models import create_game
    from app.events.models import generate_team_token

    game = await create_game(
        db,
        name=None,
        gm_token=generate_team_token(),
    )
    logger.info("Game created: id=%s gm_token=%s", game.id, game.gm_token)
    return {"token": game.gm_token}


class CreateGameRequest(BaseModel):
    name: Optional[str] = None


@app.get("/api/super-admin/games")
async def super_admin_list_games(
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_super_admin),
):
    from app.models import get_all_games

    games = await get_all_games(db)
    return {
        "games": [
            {
                "id": str(g.id),
                "name": g.name,
                "status": g.status.value,
                "gm_token": g.gm_token,
                "team_count": 0,
                "location_count": 0,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in games
        ],
    }


@app.post("/api/super-admin/games")
async def super_admin_create_game(
    body: CreateGameRequest,
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_super_admin),
):
    from app.models import create_game
    from app.events.models import generate_team_token

    game = await create_game(
        db,
        name=body.name,
        gm_token=generate_team_token(),
    )
    logger.info("Game created: id=%s gm_token=%s", game.id, game.gm_token)
    return {
        "id": str(game.id),
        "name": game.name,
        "gm_token": game.gm_token,
    }


@app.get("/api/team-state")
async def get_team_state(
    db: AsyncSession = Depends(get_api_db),
    team_token: str = Query(...),
):
    from app.team_view import get_team_view

    view = await get_team_view(team_token, db)
    if view.get("error"):
        return {"error": True}
    return view


@app.get("/api/events/stream")
async def event_stream(
    request: Request,
    team_token: Optional[str] = Query(None),
    gm_token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
):
    from app.team_view import get_team_view
    from app.models import lookup_team_token, get_game_by_gm_token

    game_id = None
    use_team_token = None

    if team_token:
        result = await lookup_team_token(db, team_token)
        if result:
            game_id, _ = result
            use_team_token = team_token

    if gm_token and not game_id:
        game = await get_game_by_gm_token(db, gm_token)
        if game:
            game_id = str(game.id)

    if not game_id:
        return HTMLResponse("Missing or invalid team_token/gm_token", status_code=400)

    if use_team_token:
        async with api_session_maker() as sse_db:
            view = await get_team_view(use_team_token, sse_db)
            if view.get("error"):
                return HTMLResponse("Unauthorized", status_code=401)

    q = await manager.connect(game_id)

    async def event_generator():
        try:
            if use_team_token:
                async with api_session_maker() as sse_db:
                    view = await get_team_view(use_team_token, sse_db)
                    yield f"data: {json.dumps(view, separators=(',', ':'))}\n\n"

            while True:
                try:
                    await asyncio.wait_for(q.get(), timeout=30)
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if use_team_token:
                    async with api_session_maker() as sse_db:
                        view = await get_team_view(use_team_token, sse_db)
                        yield f"data: {json.dumps(view, separators=(',', ':'))}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await manager.disconnect(game_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/team/{token}", response_class=HTMLResponse)
async def team_page(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_api_db),
    lang: Optional[str] = Query(None),
):
    from app.models import lookup_team_token, get_game_events

    result = await lookup_team_token(db, token)
    if not result:
        return HTMLResponse("Team not found", status_code=404)
    
    game_id_str, color = result
    game_id = uuid.UUID(game_id_str)
    
    events = await get_game_events(db, game_id)
    state = GameState.from_events(events)
    
    team_token_color = state.team_tokens.get(token)
    if team_token_color is None:
        return HTMLResponse("Team not found", status_code=404)

    if lang and lang in SUPPORTED_LANGS:
        chosen_lang = lang
    else:
        chosen_lang = request.cookies.get("lang", "")
        if chosen_lang not in SUPPORTED_LANGS:
            accept = request.headers.get("accept-language", "")
            chosen_lang = detect_language(accept)

    translations = get_translations(chosen_lang)

    response = templates.TemplateResponse(
        request,
        "team.html",
        {
            "request": request,
            "team_color": team_token_color,
            "team_token": token,
            "tr": translations,
            "tr_json": json.dumps(translations),
            "current_lang": chosen_lang,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.set_cookie(key="lang", value=chosen_lang, max_age=365 * 24 * 3600)
    return response


@app.get("/api/admin/locations")
async def get_admin_locations(
    game_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_admin_token),
):
    from app.models import get_game_locations, get_game_events
    from app.database import EventType

    if game_id is None:
        game_uuid = await _get_legacy_game_id(db)
    else:
        game_uuid = uuid.UUID(game_id)

    locations = await get_game_locations(db, game_uuid)
    events = await get_game_events(db, game_uuid)

    location_visits = {}
    for event in events:
        if event.event_type == EventType.CODE_REDEEMED:
            payload = event.payload
            location_num = payload.get("location_number")
            color = payload.get("color")
            if location_num and color:
                if location_num not in location_visits:
                    location_visits[location_num] = []
                if color not in location_visits[location_num]:
                    location_visits[location_num].append(color)

    result = []
    for loc in locations:
        result.append(
            {
                "number": loc.number,
                "code": loc.code,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "bomb_value": loc.bomb_value,
                "visited_by": location_visits.get(loc.number, []),
            }
        )

    return {"locations": result}


@app.get("/api/admin/events")
async def get_all_events_for_timeline(
    game_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_admin_token),
):
    from app.models import get_game_events

    if game_id is None:
        game_uuid = await _get_legacy_game_id(db)
    else:
        game_uuid = uuid.UUID(game_id)

    events = await get_game_events(db, game_uuid)

    return {
        "total_events": len(events),
        "events": [
            {
                "index": i,
                "id": event.id,
                "event_type": event.event_type.value
                if hasattr(event.event_type, "value")
                else event.event_type,
                "payload": event.payload,
                "player_id": event.player_id,
                "created_at": event.created_at.isoformat()
                if event.created_at
                else None,
            }
            for i, event in enumerate(events)
        ],
    }


@app.get("/api/admin/events/{event_index}/state")
async def get_state_at_event(
    event_index: int,
    game_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_admin_token),
):
    from app.models import get_game_events

    if game_id is None:
        game_uuid = await _get_legacy_game_id(db)
    else:
        game_uuid = uuid.UUID(game_id)

    events = await get_game_events(db, game_uuid)

    if event_index < 0 or event_index >= len(events):
        return {
            "error": f"Invalid event index. Must be between 0 and {len(events) - 1}"
        }

    state = GameState.from_events(events[: event_index + 1])

    return {
        "event_index": event_index,
        "total_events": len(events),
        "state": state.to_dict(),
    }


@app.get("/api/state")
async def get_game_state(
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events, get_all_players
    from app.services.ai_player import get_all_ai_players
    from app.database import Role

    game_uuid = uuid.UUID(game_id)
    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    ai_players = get_all_ai_players(game_id)

    all_players = await get_all_players(db)
    db_ai_colors = {p.color for p in all_players if p.game_id == game_uuid and p.role == Role.AI}

    teams = []
    for color, team in state.teams.items():
        is_ai = False
        if color in ai_players:
            ai = ai_players.get(color)
            if ai and hasattr(ai, "color") and ai.color == color:
                is_ai = True
        if not is_ai and color in db_ai_colors:
            is_ai = True

        token = next((t for t, c in state.team_tokens.items() if c == color), "")
        teams.append(
            {
                "name": team.name,
                "color": team.color,
                "bombs": team.bombs,
                "ships_placed": sum(team.placed_ship_types.values()),
                "ships_remaining": sum(SHIP_COUNTS.values()) - len(team.get_sunk_ships()),
                "total_ships": sum(SHIP_COUNTS.values()),
                "ships_sunk": len(team.get_sunk_ships()),
                "is_destroyed": team.is_destroyed(),
                "has_all_ships": team.has_all_ships(),
                "placed_ship_types": team.placed_ship_types,
                "is_ai": is_ai,
                "token": token,
            }
        )

    winner = state.get_winner()

    locations = []
    for num, code in state.location_codes.items():
        locations.append({"number": num, "code": code})

    return {
        "teams": teams,
        "winner": {"name": winner.name, "color": winner.color} if winner else None,
        "locations": locations,
        "available_colors": [c for c in TEAM_COLORS if c not in state.teams],
    }


@app.get("/api/board/{team_color}/public.json")
async def get_public_board_json(
    team_color: str,
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events

    events = await get_game_events(db, uuid.UUID(game_id))
    state = GameState.from_events(events)

    if team_color not in state.teams:
        return {"error": "Team not found"}

    team = state.teams[team_color]
    return _team_to_json(team, include_ships=False)


@app.get("/api/board/{team_color}/private.json")
async def get_private_board_json(
    team_color: str,
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events

    events = await get_game_events(db, uuid.UUID(game_id))
    state = GameState.from_events(events)

    if team_color not in state.teams:
        return {"error": "Team not found"}

    team = state.teams[team_color]
    return _team_to_json(team, include_ships=True)


def _team_to_json(team: "TeamState", include_ships: bool) -> TeamJsonResult:
    from app.game.ships import BOARD_SIZE

    grid: list[list[CellData]] = []
    for row in range(BOARD_SIZE):
        grid_row: list[CellData] = []
        for col in range(BOARD_SIZE):
            cell_data: CellData = {"row": row, "col": col, "status": "clear"}

            public = team.public_board[row][col]
            if public:
                attacker_color, is_hit = public
                cell_data["status"] = "hit" if is_hit else "miss"
                cell_data["attacker_color"] = attacker_color
                cell_data["is_hit"] = is_hit

            if include_ships:
                has_ship = team.private_board[row][col]
                if has_ship:
                    cell_data["has_ship"] = True
                    ship = team.get_ship_at(row, col)
                    if ship:
                        cell_data["ship_type"] = ship.ship_type
                        cell_data["ship_sunk"] = ship.is_sunk()
                else:
                    cell_data["has_ship"] = False

            grid_row.append(cell_data)
        grid.append(grid_row)

    result: TeamJsonResult = {
        "team": {"name": team.name, "color": team.color},
        "grid": grid,
    }

    if include_ships:
        result["bombs"] = team.bombs
        result["ships"] = [s.to_dict() for s in team.ships]
        result["ships_sunk"] = len(team.get_sunk_ships())
        result["is_destroyed"] = team.is_destroyed()

    return result


@app.get("/api/board/public.png")
async def get_public_boards(
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events

    events = await get_game_events(db, uuid.UUID(game_id))
    state = GameState.from_events(events)
    img = render_all_public_boards(state)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/board/{team_color}/private.png")
async def get_private_board(
    team_color: str,
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events

    events = await get_game_events(db, uuid.UUID(game_id))
    state = GameState.from_events(events)

    if team_color not in state.teams:
        return {"error": "Team not found"}

    team = state.teams[team_color]
    img = render_private_board(team)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/board/{team_color}/public.png")
async def get_public_board(
    team_color: str,
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events

    events = await get_game_events(db, uuid.UUID(game_id))
    state = GameState.from_events(events)

    if team_color not in state.teams:
        return {"error": "Team not found"}

    team = state.teams[team_color]
    img = render_board(team, show_private=False)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/board/{team_color}/replay.gif")
async def get_board_replay_gif(
    team_color: str,
    team_token: str = Query(...),
    game_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import lookup_team_token, get_game_events

    actual_game_id = game_id
    if team_token:
        result = await lookup_team_token(db, team_token)
        if result:
            actual_game_id, _ = result

    if actual_game_id is None:
        return Response("Unauthorized", status_code=401)

    game_uuid = uuid.UUID(actual_game_id)
    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.team_tokens.get(team_token) is None and game_id is None:
        return Response("Unauthorized", status_code=401)

    gif_bytes = create_public_board_gif(events, team_color)
    if not gif_bytes:
        return Response("No replay data", status_code=404)

    return Response(
        content=gif_bytes,
        media_type="image/gif",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/admin/events/{event_index}/board/public.png")
async def get_public_boards_at_event(
    event_index: int,
    game_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_admin_token),
):
    from app.models import get_game_events

    if game_id is None:
        game_uuid = await _get_legacy_game_id(db)
    else:
        game_uuid = uuid.UUID(game_id)

    events = await get_game_events(db, game_uuid)

    if event_index < 0 or event_index >= len(events):
        return {"error": f"Invalid event index"}

    state = GameState.from_events(events[: event_index + 1])
    img = render_all_public_boards(state)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/admin/events/{event_index}/board/{team_color}/public.png")
async def get_single_public_board_at_event(
    event_index: int,
    team_color: str,
    game_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_admin_token),
):
    from app.models import get_game_events

    if game_id is None:
        game_uuid = await _get_legacy_game_id(db)
    else:
        game_uuid = uuid.UUID(game_id)

    events = await get_game_events(db, game_uuid)

    if event_index < 0 or event_index >= len(events):
        return {"error": f"Invalid event index"}

    state = GameState.from_events(events[: event_index + 1])

    if team_color not in state.teams:
        return {"error": "Team not found"}

    team = state.teams[team_color]
    img = render_board(team, show_private=False)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/admin/events/{event_index}/board/{team_color}/private.png")
async def get_private_board_at_event(
    event_index: int,
    team_color: str,
    game_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
    _=Depends(verify_admin_token),
):
    from app.models import get_game_events

    if game_id is None:
        game_uuid = await _get_legacy_game_id(db)
    else:
        game_uuid = uuid.UUID(game_id)

    events = await get_game_events(db, game_uuid)

    if event_index < 0 or event_index >= len(events):
        return {"error": f"Invalid event index"}

    state = GameState.from_events(events[: event_index + 1])

    if team_color not in state.teams:
        return {"error": "Team not found"}

    team = state.teams[team_color]
    img = render_private_board(team)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/game-state.png")
async def get_game_state_png(
    game_id: str = Query(...),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import get_game_events

    events = await get_game_events(db, uuid.UUID(game_id))
    state = GameState.from_events(events)
    img = render_all_public_boards(state)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.post("/api/execute")
async def execute_command(
    cmd: ExecuteCommand,
    db: AsyncSession = Depends(get_api_db),
    auth_info: dict = Depends(verify_team_or_gm),
):
    from app.database import EventType
    from app.models import get_game_events, get_game, update_game_status

    game_id = auth_info["game_id"]
    game_uuid = uuid.UUID(game_id)
    team_color_from_auth = auth_info.get("color")

    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status == GameStatusField.ENDED:
        winner = state.get_winner()
        msg = "Game has ended! No more actions allowed."
        if winner:
            msg = f"Game has ended! {winner.name} ({winner.color}) wins!"
        return {"success": False, "message": msg}

    result = {"success": False, "message": ""}

    if cmd.command == "join":
        if state.status != GameStatusField.PREPARING:
            result["message"] = "Cannot join - game already started!"
            return result

        if cmd.team_color in state.teams:
            result["message"] = f"Team {cmd.team_color} already exists!"
            return result

        team_name = cmd.args.get("name", cmd.team_color)
        from app.events.models import TeamJoinedEvent, generate_team_token

        token = generate_team_token()
        event = TeamJoinedEvent(
            name=team_name,
            color=cmd.team_color,
            chat_id=999999,
            bombs=3,
            token=token,
        )
        state.handle_team_joined(event)
        await save_event(db, event, game_uuid)
        result["success"] = True
        result["message"] = f"Joined {team_name} as {cmd.team_color} team!"

    elif cmd.command == "rename":
        if state.status != GameStatusField.PREPARING:
            result["message"] = "Cannot rename - game already started!"
            return result

        if cmd.team_color not in state.teams:
            result["message"] = f"Team {cmd.team_color} doesn't exist!"
            return result

        new_name = cmd.args.get("name", "")
        if not new_name:
            result["message"] = "Name is required!"
            return result

        from app.events.models import TeamRenamedEvent

        event = TeamRenamedEvent(color=cmd.team_color, name=new_name)
        state, _ = event.apply(state)
        await save_event(db, event, game_uuid)
        result["success"] = True
        result["message"] = f"Renamed to {new_name}!"

    elif cmd.command == "place":
        if state.status != GameStatusField.PREPARING:
            result["message"] = "Cannot place ships - game already started!"
            return result

        if cmd.team_color not in state.teams:
            result["message"] = f"Team {cmd.team_color} doesn't exist!"
            return result

        team = state.teams[cmd.team_color]
        ship_type = cmd.args.get("ship_type")
        if not isinstance(ship_type, str):
            result["message"] = "Missing ship_type!"
            return result
        coord = cmd.args.get("coordinate", "A1")
        direction = cmd.args.get("direction", "horizontal")

        from app.game.ships import parse_coordinate

        try:
            row, col = parse_coordinate(coord)
        except ValueError as e:
            result["message"] = str(e)
            return result

        success = team.place_ship(ship_type, row, col, direction)
        if success:
            result["success"] = True
            remaining = SHIP_COUNTS.get(ship_type, 0) - team.placed_ship_types.get(
                ship_type, 0
            )
            result["message"] = (
                f"Placed {ship_type} at {coord} {direction}. Remaining: {remaining}"
            )
        else:
            result["message"] = f"Cannot place ship: check bounds and no-touching rule"

    elif cmd.command == "bomb":
        if state.status != GameStatusField.STARTED:
            result["message"] = "Cannot bomb - game hasn't started yet!"
            return result

        if cmd.team_color not in state.teams:
            result["message"] = f"Team {cmd.team_color} doesn't exist!"
            return result

        team = state.teams[cmd.team_color]
        target_color = cmd.args.get("target")
        coord = cmd.args.get("coordinate", "A1")

        if target_color not in state.teams:
            result["message"] = f"Target team {target_color} doesn't exist!"
            return result

        if team.bombs <= 0:
            result["message"] = "No bombs left!"
            return result

        from app.game.ships import parse_coordinate

        try:
            row, col = parse_coordinate(coord)
        except ValueError as e:
            result["message"] = str(e)
            return result

        target = state.teams[target_color]
        if target.is_destroyed():
            result["message"] = f"Team {target_color} is already destroyed!"
            team.bombs += 1
            return result

        if (row, col) in target.bombed_cells:
            result["message"] = f"{coord} already bombed!"
            return result

        team.bombs -= 1
        bomb_result, ship, _ = target.receive_bomb(row, col, cmd.team_color)

        from app.game.ships import parse_coordinate

        coord_str = cmd.args.get("coordinate", "A1")
        try:
            row_val, col_val = parse_coordinate(coord_str)
        except:
            row_val, col_val = 0, 0

        if bomb_result == BombResult.HIT:
            msg = f"HIT at {coord}!"
            if ship and ship.is_sunk():
                msg += f" Sunk {ship.ship_type}!"
        else:
            msg = f"MISS at {coord}!"

        result["success"] = True
        result["message"] = (
            f"Bombed {target_color} at {coord}: {msg}. Bombs left: {team.bombs}"
        )

        event = BombThrownEvent(
            attacker_color=cmd.team_color,
            target_color=target_color,
            row=row_val,
            col=col_val,
            result=bomb_result.value,
        )
        await save_event(db, event, game_uuid)

        if TELEGRAM_BOT_AVAILABLE and settings.telegram_bot_token:
            from app.models import get_player_by_color_in_game

            target_player = await get_player_by_color_in_game(db, game_uuid, target_color)
            if target_player and target_player.chat_id:
                try:
                    bot = Bot(token=settings.telegram_bot_token)
                    coord_display = coordinate_to_string(row, col)

                    if bomb_result == BombResult.HIT:
                        notify_msg = f"💥 HIT! {team.name} ({cmd.team_color}) bombed you at {coord_display}!"
                        if ship:
                            notify_msg += f" Your {ship.ship_type} was hit!"
                            if ship.is_sunk():
                                notify_msg = notify_msg.replace("was hit!", "was SUNK!")
                    else:
                        notify_msg = f"💨 MISS! {team.name} ({cmd.team_color}) missed at {coord_display}!"

                    await bot.send_message(
                        chat_id=target_player.chat_id, text=notify_msg
                    )
                except Exception as e:
                    print(f"Failed to send notification: {e}")

        winner = state.get_winner()
        if winner is not None and state.status == GameStatusField.STARTED:
            from app.database import GameStatus

            end_event = GameEndedEvent(winner=winner.name)
            await save_event(db, end_event, game_uuid)
            await update_game_status(db, game_uuid, GameStatus.ENDED)
            state.status = GameStatusField.ENDED
            result["message"] += f" 🏆 {winner.name} ({winner.color}) wins!"

    elif cmd.command == "code":
        if state.status != GameStatusField.STARTED:
            result["message"] = "Cannot redeem codes - game hasn't started yet!"
            return result

        if cmd.team_color not in state.teams:
            result["message"] = f"Team {cmd.team_color} doesn't exist!"
            return result

        team = state.teams[cmd.team_color]
        location_num = cmd.args.get("location_number")
        code = cmd.args.get("code", "")

        if location_num not in state.location_codes:
            result["message"] = f"Location {location_num} doesn't exist!"
            return result

        if state.location_codes[location_num] != code.upper():
            result["message"] = "Invalid code!"
            return result

        for event in events:
            if event.event_type == EventType.CODE_REDEEMED:
                payload = event.payload
                if (
                    payload.get("color") == cmd.team_color
                    and payload.get("location_number") == location_num
                ):
                    result["message"] = "You've already visited this location!"
                    return result

        from app.models import get_location_by_number

        location = await get_location_by_number(db, game_uuid, location_num)
        bomb_value = location.bomb_value if location else 1

        team.bombs += bomb_value
        result["success"] = True
        result["message"] = f"Code redeemed! +{bomb_value} bombs. Total: {team.bombs}"

    else:
        result["message"] = f"Unknown command: {cmd.command}"

    if result["success"]:
        if cmd.command == "place":
            from app.game.ships import parse_coordinate

            coord = cmd.args.get("coordinate", "A1")
            try:
                row, col = parse_coordinate(coord)
            except ValueError:
                row, col = 0, 0
            event = ShipPlacedEvent(
                color=cmd.team_color,
                ship_type=cmd.args.get("ship_type", ""),
                row=row,
                col=col,
                direction=cmd.args.get("direction", "horizontal"),
            )
            await save_event(db, event, game_uuid)
        elif cmd.command == "code":
            event = CodeRedeemedEvent(
                color=cmd.team_color,
                location_number=location_num,
                code=code,
                success=True,
                bombs_earned=bomb_value,
            )
            await save_event(db, event, game_uuid)

    return result


@app.post("/api/quick/add_bombs")
async def quick_add_bombs(
    action: QuickAction,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import get_game_events

    game_uuid = uuid.UUID(game_id)
    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status == GameStatusField.ENDED:
        return {"success": False, "message": "Cannot add bombs - game has ended!"}

    if action.team_color not in state.teams:
        return {"success": False, "message": f"Team {action.team_color} doesn't exist!"}

    event = BombsAddedEvent(
        color=action.team_color,
        count=action.count or 1,
    )
    new_state, updated_event = event.apply(state)

    await save_event(db, event, game_uuid)

    team = new_state.teams[action.team_color]
    return {
        "success": True,
        "message": f"Added {action.count} bombs. Total: {team.bombs}",
    }


@app.post("/api/quick/place_all_ships")
async def quick_place_all_ships(
    action: QuickAction,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.services.ship_placement import place_all_ships_game_scoped

    success, message = await place_all_ships_game_scoped(db, game_id, action.team_color)
    return {
        "success": success,
        "message": message,
    }


@app.post("/api/quick/trigger-ai-move")
async def trigger_ai_move(
    action: QuickAction,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.services.ai_player import get_ai_player, add_ai_player
    from app.database import Role
    from app.models import get_game_events, get_all_players

    game_uuid = uuid.UUID(game_id)
    ai = get_ai_player(game_id, action.team_color)

    if not ai:
        all_players = await get_all_players(db)
        for p in all_players:
            if p.game_id == game_uuid and p.color == action.team_color and p.role == Role.AI:
                ai = add_ai_player(game_id, p.color, p.name)
                break

    if not ai:
        return {
            "success": False,
            "message": f"No AI player with color {action.team_color}",
        }

    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status != GameStatusField.STARTED:
        return {"success": False, "message": "Game not started!"}

    success = await ai.execute_bomb(db, state, game_id)
    if success:
        return {"success": True, "message": f"AI {action.team_color} threw a bomb!"}
    return {
        "success": False,
        "message": f"AI {action.team_color} couldn't throw a bomb (no targets or no bombs)",
    }


@app.post("/api/quick/pause-all-ai")
async def pause_all_ai(
    game_id: str = Depends(verify_gm_token),
):
    from app.services.ai_player import pause_all_ai as pause_all

    pause_all(game_id)
    return {"success": True, "message": "All AI players paused!"}


@app.post("/api/quick/resume-all-ai")
async def resume_all_ai(
    game_id: str = Depends(verify_gm_token),
):
    from app.services.ai_player import resume_all_ai as resume_all

    resume_all(game_id)
    return {"success": True, "message": "All AI players resumed!"}


@app.post("/api/quick/add-ai")
async def quick_add_ai(
    action: AddAIAction,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.game.state import TEAM_COLORS
    from app.events import TeamJoinedEvent, save_event
    from app.database import Role

    game_uuid = uuid.UUID(game_id)
    color = action.team_color.lower()
    name = action.name or f"{color.title()} AI"

    if color not in TEAM_COLORS:
        return {
            "success": False,
            "message": f"Invalid color! Choose from: {', '.join(TEAM_COLORS)}",
        }

    from app.models import get_game_events

    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if color in state.teams:
        return {
            "success": False,
            "message": f"Team {color} already exists in game!",
        }

    from app.services.ai_player import get_ai_player

    existing_ai = get_ai_player(game_id, color)
    if existing_ai:
        return {"success": False, "message": f"AI player for {color} already exists!"}

    from app.models import create_player
    from sqlalchemy import select
    from app.database import Player

    result = await db.execute(select(Player).where(Player.game_id == game_uuid, Player.color == color))
    old_player = result.scalar_one_or_none()
    if old_player:
        await db.delete(old_player)
        await db.commit()

    await create_player(db, game_uuid, name, color, None, Role.AI)

    from app.events.models import generate_team_token

    token = generate_team_token()
    event = TeamJoinedEvent(name=name, color=color, chat_id=0, bombs=3, token=token)
    await save_event(db, event, game_uuid)

    from app.services.ai_player import add_ai_player

    add_ai_player(game_id, color, name)

    from app.services.ship_placement import place_all_ships_game_scoped

    await place_all_ships_game_scoped(db, game_id, color)

    return {
        "success": True,
        "message": f"🤖 Added AI player '{name}' ({color})! Ships auto-placed.",
    }


@app.post("/api/quick/reset_team")
async def quick_reset_team(
    action: QuickAction,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import get_game_events

    game_uuid = uuid.UUID(game_id)
    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if action.team_color not in state.teams:
        return {"success": False, "message": f"Team {action.team_color} doesn't exist!"}

    event = TeamResetEvent(
        color=action.team_color,
    )
    new_state, updated_event = event.apply(state)

    await save_event(db, event, game_uuid)

    return {"success": True, "message": f"Reset team {action.team_color}!"}


@app.post("/api/quick/remove_ship")
async def quick_remove_ship(
    action: RemoveShipAction,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import get_game_events

    game_uuid = uuid.UUID(game_id)
    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status != GameStatusField.PREPARING:
        return {
            "success": False,
            "message": "Cannot remove ships - game has already started!",
        }

    if action.team_color not in state.teams:
        return {"success": False, "message": f"Team {action.team_color} doesn't exist!"}

    event = ShipRemovedEvent(
        color=action.team_color,
        row=action.row,
        col=action.col,
    )
    new_state, updated_event = event.apply(state)

    if not updated_event.success:
        return {
            "success": False,
            "message": f"Failed to remove ship: {updated_event.reason}",
        }

    await save_event(db, updated_event, game_uuid)

    return {
        "success": True,
        "message": f"Removed {updated_event.ship_type} from {action.team_color}!",
    }


class CreateLocations(BaseModel):
    latitude: float
    longitude: float
    count: int = 10
    radius_km: float = 2.0


@app.post("/api/quick/create_locations")
async def create_locations(
    action: CreateLocations,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import get_game_locations, get_next_location_number, create_location
    from app.database import Location

    game_uuid = uuid.UUID(game_id)

    from app.models import get_game_events

    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status != GameStatusField.PREPARING:
        return {
            "success": False,
            "message": "Cannot create locations - game already started!",
        }

    existing_locations = await get_game_locations(db, game_uuid)
    if len(existing_locations) + action.count > 100:
        return {
            "success": False,
            "message": f"Cannot create {action.count} locations! Would exceed 100 maximum. Current: {len(existing_locations)}",
        }

    total_after = len(existing_locations) + action.count
    default_bomb_value = max(1, 100 // total_after)

    for loc in existing_locations:
        loc.bomb_value = default_bomb_value

    created = []

    for i in range(action.count):
        if action.radius_km > 0:
            lat_offset = random.uniform(-action.radius_km / 111, action.radius_km / 111)
            lon_offset = random.uniform(
                -action.radius_km / (111 * math.cos(action.latitude * math.pi / 180)),
                action.radius_km / (111 * math.cos(action.latitude * math.pi / 180)),
            )
            lat = action.latitude + lat_offset
            lon = action.longitude + lon_offset
        else:
            lat = action.latitude
            lon = action.longitude

        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))

        number = await get_next_location_number(db, game_uuid)

        new_location = Location(
            game_id=game_uuid,
            number=number,
            latitude=lat,
            longitude=lon,
            code=code,
            bomb_value=default_bomb_value,
        )
        db.add(new_location)

        event = LocationAddedEvent(
            number=number,
            latitude=lat,
            longitude=lon,
            code=code,
            bomb_value=default_bomb_value,
        )
        await save_event(db, event, game_uuid)

        created.append({"number": number, "code": code, "lat": lat, "lon": lon})

    await db.commit()

    return {
        "success": True,
        "message": f"Created {len(created)} locations! Each worth {default_bomb_value} bombs (Total: 100)",
        "locations": created,
        "bomb_value": default_bomb_value,
    }


class RemoveLocation(BaseModel):
    location_number: int


@app.post("/api/quick/remove_location")
async def remove_location(
    action: RemoveLocation,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import get_location_by_number, get_game_locations, get_game_events
    from app.database import Location
    from app.events.models import LocationRemovedEvent

    game_uuid = uuid.UUID(game_id)

    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status == GameStatusField.ENDED:
        return {
            "success": False,
            "message": "Cannot remove location - game has ended!",
        }

    location = await get_location_by_number(db, game_uuid, action.location_number)
    if not location:
        return {
            "success": False,
            "message": f"Location {action.location_number} doesn't exist!",
        }

    existing_locations = await get_game_locations(db, game_uuid)
    remaining_count = len(existing_locations) - 1

    was_visited = False
    for event in events:
        if event.event_type == EventType.CODE_REDEEMED:
            payload = event.payload
            if payload.get("location_number") == action.location_number:
                was_visited = True
                break

    await db.delete(location)

    if remaining_count > 0:
        new_bomb_value = max(1, 100 // remaining_count)
        for loc in existing_locations:
            if loc.number != action.location_number:
                loc.bomb_value = new_bomb_value
    else:
        new_bomb_value = 0

    event = LocationRemovedEvent(
        number=action.location_number,
        bomb_value=location.bomb_value,
    )
    await save_event(db, event, game_uuid)

    await db.commit()

    warning = ""
    if was_visited:
        warning = "Warning: This location had already been visited!"

    return {
        "success": True,
        "message": f"Location {action.location_number} removed. All locations now worth {new_bomb_value} bombs (Total: {100 if remaining_count > 0 else 0}). {warning}".strip(),
        "locations_remaining": remaining_count,
        "bomb_value": new_bomb_value,
        "was_visited": was_visited,
    }


@app.post("/api/quick/reset-game")
async def reset_game(
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import delete_all_events, update_game_status
    from app.database import GameStatus

    game_uuid = uuid.UUID(game_id)
    count = await delete_all_events(db, game_uuid)
    await update_game_status(db, game_uuid, GameStatus.WAITING, started_at=None)

    return {
        "success": True,
        "message": f"Game reset! Deleted {count} events. Teams can rejoin.",
    }


@app.post("/api/quick/clear-locations")
async def clear_locations(
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import delete_all_locations

    game_uuid = uuid.UUID(game_id)
    count = await delete_all_locations(db, game_uuid)

    return {
        "success": True,
        "message": f"Cleared {count} locations!",
    }


@app.post("/api/quick/reset-settings")
async def reset_settings(
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import update_game_status, get_game
    from app.database import GameStatus

    game_uuid = uuid.UUID(game_id)
    game = await get_game(db, game_uuid)
    await update_game_status(db, game_uuid, GameStatus.WAITING, started_at=None)
    status_val = game.status.value if game else "WAITING"

    return {
        "success": True,
        "message": f"Settings reset! Status: {status_val}",
    }


@app.post("/api/quick/clear-players")
async def clear_players(
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import delete_all_players

    game_uuid = uuid.UUID(game_id)
    count = await delete_all_players(db, game_uuid)

    return {
        "success": True,
        "message": f"Cleared {count} teams!",
    }


@app.post("/api/quick/clear-database")
async def clear_database(
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.events.models import generate_team_token
    from app.models import (
        delete_all_players,
        delete_all_events,
        delete_all_locations,
    )
    from app.database import GameStatus

    game_uuid = uuid.UUID(game_id)

    players_count = await delete_all_players(db, game_uuid)
    events_count = await delete_all_events(db, game_uuid)
    locations_count = await delete_all_locations(db, game_uuid)

    from app.models import update_game_status

    await update_game_status(db, game_uuid, GameStatus.WAITING, started_at=None)

    return {
        "success": True,
        "message": f"Database cleared! Players: {players_count}, Events: {events_count}, Locations: {locations_count}.",
    }


@app.post("/api/quick/start-game")
async def start_game(
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import get_game_locations, update_game_status, get_game
    from app.database import GameStatus
    from datetime import datetime, timezone

    game_uuid = uuid.UUID(game_id)

    from app.models import get_game_events

    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    locations = await get_game_locations(db, game_uuid)

    if state.status == GameStatusField.STARTED:
        return {"success": False, "message": "Game has already started!"}

    if state.status == GameStatusField.ENDED:
        return {"success": False, "message": "Game has ended! Reset first."}

    if len(state.teams) < 2:
        return {
            "success": False,
            "message": f"Cannot start game - need at least 2 teams, currently have {len(state.teams)}",
        }

    teams_without_ships = [t.name for t in state.teams.values() if not t.has_all_ships()]
    if teams_without_ships:
        return {
            "success": False,
            "message": f"Cannot start game - not all teams have placed all ships: {', '.join(teams_without_ships)}",
        }

    if len(locations) == 0:
        return {
            "success": False,
            "message": "Cannot start game - no locations defined!",
        }

    event = GameStartedEvent()
    new_state, updated_event = event.apply(state)
    await save_event(db, updated_event, game_uuid)

    await update_game_status(db, game_uuid, GameStatus.STARTED, started_at=datetime.now(timezone.utc))

    return {
        "success": True,
        "message": "Game started! Teams can now bomb and redeem codes.",
    }


@app.post("/api/quick/end-game")
async def end_game(
    winner: str = "",
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import update_game_status
    from app.database import GameStatus

    game_uuid = uuid.UUID(game_id)

    from app.models import get_game_events

    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status == GameStatusField.PREPARING:
        return {"success": False, "message": "Game hasn't started yet!"}

    if state.status == GameStatusField.ENDED:
        return {"success": False, "message": "Game has already ended!"}

    event = GameEndedEvent(winner=winner)
    new_state, updated_event = event.apply(state)
    await save_event(db, updated_event, game_uuid)

    await update_game_status(db, game_uuid, GameStatus.ENDED)

    return {
        "success": True,
        "message": f"Game ended! Winner: {winner if winner else 'No winner'}",
    }


@app.get("/api/game-status")
async def get_game_status(
    game_id: Optional[str] = Query(None),
    gm_token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_api_db),
):
    from app.models import (
        get_game_locations,
        get_game_events,
        get_game,
        get_game_by_gm_token,
    )
    from app.game.state import GameState

    actual_game_id = game_id

    if gm_token:
        game = await get_game_by_gm_token(db, gm_token)
        if game:
            actual_game_id = str(game.id)

    if actual_game_id is None:
        game_uuid = await _get_legacy_game_id(db)
    else:
        game_uuid = uuid.UUID(actual_game_id)

    game = await get_game(db, game_uuid)
    locations = await get_game_locations(db, game_uuid)
    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    teams_with_all_ships = sum(
        1 for team in state.teams.values() if team.has_all_ships()
    )

    return {
        "status": game.status.value if game else "PREPARING",
        "locations_placed": len(locations),
        "total_locations_needed": 0,
        "total_teams": len(state.teams),
        "teams_with_all_ships": teams_with_all_ships,
    }


class SetLocationBombs(BaseModel):
    location_number: int
    bomb_value: int


@app.post("/api/quick/set_location_bombs")
async def set_location_bombs(
    data: SetLocationBombs,
    db: AsyncSession = Depends(get_api_db),
    game_id: str = Depends(verify_gm_token),
):
    from app.models import get_location_by_number

    game_uuid = uuid.UUID(game_id)
    location = await get_location_by_number(db, game_uuid, data.location_number)
    if not location:
        return {
            "success": False,
            "message": f"Location {data.location_number} does not exist!",
        }

    if data.bomb_value < 1:
        return {"success": False, "message": "Bomb value must be at least 1!"}

    location.bomb_value = data.bomb_value
    await db.commit()

    return {
        "success": True,
        "message": f"Location {data.location_number} now worth {data.bomb_value} bombs!",
    }
