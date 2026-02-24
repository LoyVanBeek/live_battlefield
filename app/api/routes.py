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
import asyncio

from app.config import settings
from app.models import get_all_events
from app.database import EventType
from app.game.state import GameState, TEAM_COLORS
from app.game.board import (
    render_all_public_boards,
    render_private_board,
    boards_to_bytes,
)
from app.game.ships import (
    SHIP_SIZES,
    SHIP_COUNTS,
    VALID_SHIP_TYPES,
    coordinate_to_string,
)
from app.game.state import BombResult

try:
    from telegram import Bot

    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    Bot = None

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
                "bomb_value": loc.bomb_value,
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
                "bomb_value": loc.bomb_value,
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
    from app.database import EventType

    events = await get_all_events(db)
    state = GameState.from_events(events)

    result = {"success": False, "message": ""}

    if cmd.command == "join":
        if cmd.team_color in state.teams:
            result["message"] = f"Team {cmd.team_color} already exists!"
            return result

        team_name = cmd.args.get("name", cmd.team_color)
        state.handle_team_joined(
            {"name": team_name, "color": cmd.team_color, "chat_id": 999999, "bombs": 0}
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

        await add_event(db, EventType.BOMB_THROWN, payload)

        # Send notification to target player
        if TELEGRAM_BOT_AVAILABLE and settings.telegram_bot_token:
            from app.models import get_player_by_color

            target_player = await get_player_by_color(db, target_color)
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

        for event in events:
            if event.event_type == EventType.CODE_REDEEMED:
                payload = event.payload
                if (
                    payload.get("color") == cmd.team_color
                    and payload.get("location_number") == location_num
                ):
                    result["message"] = "You've already visited this location!"
                    return result

        # Get location's bomb value from database (source of truth)
        from app.models import get_location_by_number

        location = await get_location_by_number(db, location_num)
        bomb_value = location.bomb_value if location else 1

        team.bombs += bomb_value
        result["success"] = True
        result["message"] = f"Code redeemed! +{bomb_value} bombs. Total: {team.bombs}"

    else:
        result["message"] = f"Unknown command: {cmd.command}"

    from app.models import add_event
    from app.database import EventType

    if result["success"]:
        payload = {"color": cmd.team_color, "command": cmd.command, **cmd.args}
        if cmd.command == "place":
            await add_event(db, EventType.SHIP_PLACED, payload)
        elif cmd.command == "code":
            payload["bombs_earned"] = bomb_value
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
            while attempts < 5000:
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
            "success": False,
            "message": f"Placed {len(placed)} ships. Failed: {failed}",
            "ships_placed": sum(team.placed_ship_types.values()),
        }
    return {
        "success": True,
        "message": f"Placed all {len(placed)} ships successfully!",
        "ships_placed": sum(team.placed_ship_types.values()),
    }


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
    from app.models import get_all_locations, get_next_location_number, add_event
    from app.database import EventType, Location

    # Check existing locations
    existing_locations = await get_all_locations(db)
    if len(existing_locations) + action.count > 100:
        return {
            "success": False,
            "message": f"Cannot create {action.count} locations! Would exceed 100 maximum. Current: {len(existing_locations)}",
        }

    # Calculate default bomb value - total should equal 100
    total_after = len(existing_locations) + action.count
    default_bomb_value = max(1, 100 // total_after)

    # Update ALL existing locations to have equal bomb values
    for loc in existing_locations:
        loc.bomb_value = default_bomb_value

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

        number = await get_next_location_number(db)

        new_location = Location(
            number=number,
            latitude=lat,
            longitude=lon,
            code=code,
            bomb_value=default_bomb_value,
        )
        db.add(new_location)

        await add_event(
            db,
            EventType.LOCATION_ADDED,
            {
                "number": number,
                "latitude": lat,
                "longitude": lon,
                "code": code,
                "bomb_value": default_bomb_value,
            },
        )

        created.append({"number": number, "code": code, "lat": lat, "lon": lon})

    await db.commit()

    return {
        "success": True,
        "message": f"Created {len(created)} locations! Each worth {default_bomb_value} bombs (Total: 100)",
        "locations": created,
        "bomb_value": default_bomb_value,
    }


@app.post("/api/quick/reset-game")
async def reset_game(db: AsyncSession = Depends(get_api_db)):
    from app.models import delete_all_events
    from app.database import GameStatus

    count = await delete_all_events(db)
    await update_game_settings(db, status=GameStatus.WAITING, started_at=None)

    return {
        "success": True,
        "message": f"Game reset! Deleted {count} events. Teams can rejoin.",
    }


@app.post("/api/quick/clear-locations")
async def clear_locations(db: AsyncSession = Depends(get_api_db)):
    from app.models import delete_all_locations

    count = await delete_all_locations(db)

    return {
        "success": True,
        "message": f"Cleared {count} locations!",
    }


@app.post("/api/quick/reset-settings")
async def reset_settings(db: AsyncSession = Depends(get_api_db)):
    from app.models import reset_game_settings

    settings = await reset_game_settings(db)

    return {
        "success": True,
        "message": f"Settings reset! Status: {settings.status.value}, Locations needed: {settings.total_locations_needed}",
    }


@app.post("/api/quick/clear-players")
async def clear_players(db: AsyncSession = Depends(get_api_db)):
    from app.models import delete_all_players

    count = await delete_all_players(db)

    return {
        "success": True,
        "message": f"Cleared {count} teams!",
    }


@app.post("/api/quick/clear-database")
async def clear_database(db: AsyncSession = Depends(get_api_db)):
    from app.models import (
        delete_all_players,
        delete_all_events,
        delete_all_locations,
        reset_game_settings,
    )
    from app.database import GameStatus

    players_count = await delete_all_players(db)
    events_count = await delete_all_events(db)
    locations_count = await delete_all_locations(db)
    await reset_game_settings(db)

    return {
        "success": True,
        "message": f"Database cleared! Players: {players_count}, Events: {events_count}, Locations: {locations_count}. Settings reset.",
    }


async def update_game_settings(db: AsyncSession, **kwargs):
    from app.models import get_or_create_game_settings
    from app.database import GameSettings as DBGameSettings

    settings = await get_or_create_game_settings(db)
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await db.commit()
    await db.refresh(settings)
    return settings


@app.post("/api/quick/start-game")
async def start_game(db: AsyncSession = Depends(get_api_db)):
    from app.models import get_or_create_game_settings
    from app.database import GameStatus

    settings = await get_or_create_game_settings(db)

    if settings.status == GameStatus.STARTED:
        return {"success": False, "message": "Game has already started!"}

    if settings.status == GameStatus.ENDED:
        return {"success": False, "message": "Game has ended! Reset first."}

    await update_game_settings(db, status=GameStatus.STARTED)

    return {
        "success": True,
        "message": "Game started! Teams can now bomb and redeem codes.",
    }


@app.get("/api/game-status")
async def get_game_status(db: AsyncSession = Depends(get_api_db)):
    from app.models import (
        get_or_create_game_settings,
        get_all_locations,
        get_all_events,
    )
    from app.game.state import GameState

    settings = await get_or_create_game_settings(db)
    locations = await get_all_locations(db)
    events = await get_all_events(db)
    state = GameState.from_events(events)

    teams_with_all_ships = sum(
        1 for team in state.teams.values() if team.has_all_ships()
    )

    return {
        "status": settings.status.value,
        "locations_placed": len(locations),
        "total_locations_needed": settings.total_locations_needed,
        "total_teams": len(state.teams),
        "teams_with_all_ships": teams_with_all_ships,
    }


class SetLocationBombs(BaseModel):
    location_number: int
    bomb_value: int


@app.post("/api/quick/set_location_bombs")
async def set_location_bombs(
    data: SetLocationBombs, db: AsyncSession = Depends(get_api_db)
):
    from app.models import get_location_by_number

    location = await get_location_by_number(db, data.location_number)
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
