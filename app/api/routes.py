from fastapi import FastAPI, Depends, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pydantic import BaseModel
from typing import Optional, Any, Dict
import os
import math
import random
import string

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
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/map")


@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})


@app.get("/api/locations")
async def get_public_locations(db: AsyncSession = Depends(get_api_db)):
    from app.models import get_all_locations

    locations = await get_all_locations(db)

    return {
        "locations": [
            {
                "number": loc.number,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
            }
            for loc in locations
        ]
    }


@app.get("/api/public-state")
async def get_public_state(db: AsyncSession = Depends(get_api_db)):
    from app.models import get_or_create_game_settings
    from app.game.state import GameState

    settings = await get_or_create_game_settings(db)
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
                "ships_sunk": len(team.get_sunk_ships()),
            }
        )

    return {
        "status": settings.status.value,
        "teams": teams,
    }


@app.get("/admin/test-panel", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_redirect(request: Request):
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/admin/test-panel")


@app.get("/admin/locations-secret", response_class=HTMLResponse)
async def locations_page(request: Request):
    return templates.TemplateResponse("locations.html", {"request": request})


@app.get("/api/admin/locations")
async def get_admin_locations(db: AsyncSession = Depends(get_api_db)):
    from app.models import get_all_locations
    from app.database import EventType

    locations = await get_all_locations(db)
    events = await get_all_events(db)

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
                "visited_by": location_visits.get(loc.number, []),
            }
        )

    return {"locations": result}


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

        payload = {
            "color": cmd.team_color,
            "command": cmd.command,
            **cmd.args,
            "attacker_color": cmd.team_color,
            "target_color": target_color,
            "row": row_val,
            "col": col_val,
            "result": bomb_result.value,
        }

        from app.models import add_event
        from app.database import EventType

        await add_event(db, EventType.BOMB_THROWN, payload)

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

    if result["success"]:
        payload = {"color": cmd.team_color, "command": cmd.command, **cmd.args}
        if cmd.command == "place":
            await add_event(db, EventType.SHIP_PLACED, payload)
        elif cmd.command == "code":
            await add_event(db, EventType.CODE_REDEEMED, payload)
        elif cmd.command == "join":
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

                    from app.models import add_event
                    from app.database import EventType

                    await add_event(
                        db,
                        EventType.SHIP_PLACED,
                        {
                            "color": action.team_color,
                            "ship_type": ship_type,
                            "row": row,
                            "col": col,
                            "direction": direction,
                        },
                    )
                    break
                attempts += 1
            else:
                failed.append(ship_type)

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


class CreateLocations(BaseModel):
    latitude: float
    longitude: float
    count: int = 10
    radius_km: float = 2.0


@app.post("/api/quick/create_locations")
async def create_locations(
    action: CreateLocations, db: AsyncSession = Depends(get_api_db)
):
    created = []

    for i in range(action.count):
        lat_offset = random.uniform(-action.radius_km / 111, action.radius_km / 111)
        lon_offset = random.uniform(
            -action.radius_km / (111 * math.cos(action.latitude * math.pi / 180)),
            action.radius_km / (111 * math.cos(action.latitude * math.pi / 180)),
        )

        lat = action.latitude + lat_offset
        lon = action.longitude + lon_offset

        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))

        from app.models import create_location
        from app.models import get_next_location_number

        number = await get_next_location_number(db)
        await create_location(db, number, lat, lon, code)

        from app.models import add_event
        from app.database import EventType

        await add_event(
            db,
            EventType.LOCATION_ADDED,
            {"number": number, "latitude": lat, "longitude": lon, "code": code},
        )

        created.append({"number": number, "code": code, "lat": lat, "lon": lon})

    return {
        "success": True,
        "message": f"Created {len(created)} locations!",
        "locations": created,
    }
