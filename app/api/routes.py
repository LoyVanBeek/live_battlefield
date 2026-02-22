from fastapi import FastAPI, Depends, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pydantic import BaseModel
from typing import Optional, Any, Dict
import os

from app.config import settings
from app.models import get_all_events
from app.game.state import GameState, TEAM_COLORS
from app.game.board import (
    render_all_public_boards,
    render_private_board,
    boards_to_bytes,
)
from app.game.ships import SHIP_SIZES, SHIP_COUNTS, VALID_SHIP_TYPES
from app.game.state import BombResult

api_engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
api_session_maker = async_sessionmaker(
    api_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_api_db():
    async with api_session_maker() as session:
        yield session


app = FastAPI(title="Live Battlefield API")

templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


class ExecuteCommand(BaseModel):
    team_color: str
    command: str
    args: dict[str, Any]


class QuickAction(BaseModel):
    team_color: str
    count: Optional[int] = 1


@app.get("/")
async def root():
    return {"message": "Live Battlefield API", "admin": "/admin"}


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/api/state")
async def get_game_state(db: AsyncSession = Depends(get_api_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)

    teams = []
    for color, team in state.teams.items():
        teams.append(
            {
                "name": team.name,
                "color": team.color,
                "bombs": team.bombs,
                "ships_placed": sum(team.placed_ship_types.values()),
                "total_ships": sum(SHIP_COUNTS.values()),
                "ships_sunk": len(team.get_sunk_ships()),
                "is_destroyed": team.is_destroyed(),
                "has_all_ships": team.has_all_ships(),
                "placed_ship_types": team.placed_ship_types,
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


@app.get("/api/board/public.png")
async def get_public_boards(db: AsyncSession = Depends(get_api_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)
    img = render_all_public_boards(state)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/board/{team_color}/private.png")
async def get_private_board(team_color: str, db: AsyncSession = Depends(get_api_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)

    if team_color not in state.teams:
        return {"error": "Team not found"}

    team = state.teams[team_color]
    img = render_private_board(team)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/game-state.png")
async def get_game_state_png(db: AsyncSession = Depends(get_api_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)
    img = render_all_public_boards(state)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.post("/api/execute")
async def execute_command(cmd: ExecuteCommand, db: AsyncSession = Depends(get_api_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)

    result = {"success": False, "message": ""}

    if cmd.command == "join":
        if cmd.team_color in state.teams:
            result["message"] = f"Team {cmd.team_color} already exists!"
            return result

        team_name = cmd.args.get("name", cmd.team_color)
        state.handle_team_joined(
            {"name": team_name, "color": cmd.team_color, "chat_id": 999999, "bombs": 3}
        )
        result["success"] = True
        result["message"] = f"Joined {team_name} as {cmd.team_color} team!"

    elif cmd.command == "place":
        if cmd.team_color not in state.teams:
            result["message"] = f"Team {cmd.team_color} doesn't exist!"
            return result

        team = state.teams[cmd.team_color]
        ship_type = cmd.args.get("ship_type")
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
        if (row, col) in target.bombed_cells:
            result["message"] = f"{coord} already bombed!"
            return result

        team.bombs -= 1
        bomb_result, ship = target.receive_bomb(row, col, cmd.team_color)

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

    elif cmd.command == "code":
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

        team.bombs += 1
        result["success"] = True
        result["message"] = f"Code redeemed! Bombs: {team.bombs}"

    else:
        result["message"] = f"Unknown command: {cmd.command}"

    from app.models import add_event
    from app.database import EventType

    payload = {"color": cmd.team_color, "command": cmd.command, **cmd.args}
    if result["success"]:
        payload["executed"] = True
        await add_event(db, EventType.TEAM_JOINED, payload)

    return result


@app.post("/api/quick/add_bombs")
async def quick_add_bombs(action: QuickAction, db: AsyncSession = Depends(get_api_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)

    if action.team_color not in state.teams:
        return {"success": False, "message": f"Team {action.team_color} doesn't exist!"}

    team = state.teams[action.team_color]
    team.bombs += action.count

    from app.models import add_event
    from app.database import EventType

    await add_event(
        db,
        EventType.TEAM_JOINED,
        {
            "color": action.team_color,
            "quick_action": "add_bombs",
            "count": action.count,
        },
    )

    return {
        "success": True,
        "message": f"Added {action.count} bombs. Total: {team.bombs}",
    }


@app.post("/api/quick/place_all_ships")
async def quick_place_all_ships(
    action: QuickAction, db: AsyncSession = Depends(get_api_db)
):
    events = await get_all_events(db)
    state = GameState.from_events(events)

    if action.team_color not in state.teams:
        return {"success": False, "message": f"Team {action.team_color} doesn't exist!"}

    team = state.teams[action.team_color]

    import random

    placed = []
    failed = []

    for ship_type, count in SHIP_COUNTS.items():
        for i in range(count):
            attempts = 0
            while attempts < 100:
                row = random.randint(0, 9)
                col = random.randint(0, 9)
                direction = random.choice(["horizontal", "vertical"])

                if team.place_ship(ship_type, row, col, direction):
                    from app.game.ships import coordinate_to_string

                    coord = coordinate_to_string(row, col)
                    placed.append(f"{ship_type} at {coord} {direction}")
                    break
                attempts += 1
            else:
                failed.append(ship_type)

    from app.models import add_event
    from app.database import EventType

    await add_event(
        db,
        EventType.SHIP_PLACED,
        {
            "color": action.team_color,
            "quick_action": "place_all_ships",
            "placed": placed,
            "failed": failed,
        },
    )

    if failed:
        return {
            "success": True,
            "message": f"Placed {len(placed)} ships. Failed: {failed}",
        }
    return {"success": True, "message": f"Placed all {len(placed)} ships successfully!"}


@app.post("/api/quick/reset_team")
async def quick_reset_team(action: QuickAction, db: AsyncSession = Depends(get_api_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)

    if action.team_color not in state.teams:
        return {"success": False, "message": f"Team {action.team_color} doesn't exist!"}

    team = state.teams[action.team_color]
    team.ships = []
    team.placed_ship_types = {}
    team.private_board = [[False] * 10 for _ in range(10)]
    team.public_board = [[None] * 10 for _ in range(10)]
    team.bombed_cells = []

    from app.models import add_event
    from app.database import EventType

    await add_event(
        db,
        EventType.TEAM_JOINED,
        {"color": action.team_color, "quick_action": "reset_team"},
    )

    return {"success": True, "message": f"Reset team {action.team_color}!"}
