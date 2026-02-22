from app.game.ships import (
    SHIP_SIZES,
    SHIP_COUNTS,
    VALID_SHIP_TYPES,
    VALID_DIRECTIONS,
    parse_coordinate,
    coordinate_to_string,
)
from app.game.state import GameState, BombResult
from app.game.board import (
    render_all_public_boards,
    render_private_board,
    boards_to_bytes,
)
from app.database import EventType, Role
from app.models import (
    get_player_by_chat,
    get_player_by_id,
    get_player_by_color,
    create_player,
    get_all_teams,
    get_all_game_masters,
    add_event,
    get_all_events,
    get_location_by_number,
    create_location,
    get_next_location_number,
    get_all_locations,
)
from app.bot.helpers import send_message, send_photo
from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional
import math
import random
import string
import secrets


def generate_code(length: int = 4) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def handle_join(
    db, update: Update, context: ContextTypes.DEFAULT_TYPE, team_name: str
):
    chat_id = update.effective_chat.id

    existing_player = await get_player_by_chat(db, chat_id)
    if existing_player:
        return "You have already joined the game!"

    events = await get_all_events(db)
    state = GameState.from_events(events)

    from app.models import get_or_create_game_settings

    settings = await get_or_create_game_settings(db)

    if settings.status.value == "started":
        return "The game has already started! No new teams can join."

    if settings.status.value == "ended":
        return "The game has ended! Use /resetgame to start a new game."

    if state.is_team_name_taken(team_name):
        return f"Team name '{team_name}' is already taken!"

    color = state.get_next_color()
    if not color:
        return "No more colors available! The game is full."

    player = await create_player(db, team_name, color, chat_id)

    await add_event(
        db,
        EventType.TEAM_JOINED,
        {"name": team_name, "color": color, "chat_id": chat_id, "bombs": 3},
        player.id,
    )

    return f"Welcome {team_name}! You are the {color} team.\nYou have 3 bombs to start."


async def handle_place(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ship_type: str,
    coord: str,
    direction: str,
):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    if ship_type not in VALID_SHIP_TYPES:
        return f"Invalid ship type. Valid types: {', '.join(VALID_SHIP_TYPES)}"

    if direction not in VALID_DIRECTIONS:
        return f"Invalid direction. Use 'horizontal' or 'vertical'"

    try:
        row, col = parse_coordinate(coord)
    except ValueError as e:
        return str(e)

    events = await get_all_events(db)
    state = GameState.from_events(events)

    if player.color not in state.teams:
        return "You are not in the game yet!"

    team = state.teams[player.color]

    if not team.can_place_ship(ship_type):
        return f"You've already placed all your {ship_type} ships!"

    success = team.place_ship(ship_type, row, col, direction)
    if not success:
        return "Cannot place ship there! Check boundaries and that ships don't touch."

    await add_event(
        db,
        EventType.SHIP_PLACED,
        {
            "color": player.color,
            "ship_type": ship_type,
            "row": row,
            "col": col,
            "direction": direction,
        },
        player.id,
    )

    img = render_private_board(team)
    img_bytes = boards_to_bytes(img)

    await send_photo(
        context,
        chat_id,
        img_bytes,
        caption=f"Ship placed! Ships left: {SHIP_COUNTS[ship_type] - team.placed_ship_types.get(ship_type, 0)}",
    )

    return None


async def handle_bomb(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_color: str,
    coord: str,
):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    try:
        row, col = parse_coordinate(coord)
    except ValueError as e:
        return str(e)

    events = await get_all_events(db)
    state = GameState.from_events(events)

    from app.models import get_or_create_game_settings

    settings = await get_or_create_game_settings(db)

    if settings.status.value != "started":
        return "The game hasn't started yet! Waiting for all ships and locations to be ready."

    if player.color not in state.teams:
        return "You are not in the game yet!"

    attacker = state.teams[player.color]

    if attacker.bombs <= 0:
        return "You have no bombs! Visit locations to earn more."

    if target_color not in state.teams:
        return f"Team '{target_color}' does not exist!"

    if target_color == player.color:
        return "You cannot bomb yourself!"

    target = state.teams[target_color]

    if (row, col) in target.bombed_cells:
        return f"That coordinate has already been bombed!"

    attacker.bombs -= 1
    result, ship = target.receive_bomb(row, col, player.color)

    await add_event(
        db,
        EventType.BOMB_THROWN,
        {
            "attacker_color": player.color,
            "target_color": target_color,
            "row": row,
            "col": col,
            "result": result.value,
        },
        player.id,
    )

    target_player = await get_player_by_color(db, target_color)
    if target_player:
        coord_str = coordinate_to_string(row, col)
        if result == BombResult.HIT:
            hit_msg = (
                f"💥 HIT! {attacker.name} ({attacker.color}) bombed you at {coord_str}!"
            )
            if ship:
                hit_msg += f" Your {ship.ship_type} was hit!"
                if ship.is_sunk():
                    hit_msg = hit_msg.replace("was hit!", "was SUNK!")
        else:
            hit_msg = (
                f"💨 MISS! {attacker.name} ({attacker.color}) missed at {coord_str}!"
            )
        await send_message(context, target_player.chat_id, hit_msg)

    if result == BombResult.HIT:
        msg = f"You bombed {target.name} at {coord}! 💥 HIT!"
        if ship:
            msg += f" You hit their {ship.ship_type}!"
            if ship.is_sunk():
                msg = msg.replace("You hit their", "You SUNK their")
    else:
        msg = f"You bombed {target.name} at {coord}. 💨 MISS!"

    msg += f"\nBombs remaining: {attacker.bombs}"

    winner = state.get_winner()
    if winner:
        msg += f"\n\n🏆 {winner.name} ({winner.color}) WINS!"

    return msg


async def handle_code(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    location_number: int,
    code: str,
):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    location = await get_location_by_number(db, location_number)
    if not location:
        return f"Location {location_number} does not exist!"

    events = await get_all_events(db)
    state = GameState.from_events(events)

    from app.models import get_or_create_game_settings

    settings = await get_or_create_game_settings(db)

    if settings.status.value != "started":
        return (
            "The game hasn't started yet! Wait for all ships and locations to be ready."
        )

    if player.color not in state.teams:
        return "You are not in the game yet!"

    team = state.teams[player.color]

    if location.code.upper() != code.upper():
        return "Invalid code! Please check the code at the location."

    events = await get_all_events(db)
    for event in events:
        if event.event_type == EventType.CODE_REDEEMED:
            payload = event.payload
            if (
                payload.get("color") == player.color
                and payload.get("location_number") == location_number
            ):
                return "You've already visited this location!"

    team.bombs += 1

    await add_event(
        db,
        EventType.CODE_REDEEMED,
        {
            "color": player.color,
            "location_number": location_number,
            "code": code.upper(),
            "success": True,
        },
        player.id,
    )

    return f"Correct! +1 bomb added. You now have {team.bombs} bombs."


async def handle_overview(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    events = await get_all_events(db)
    state = GameState.from_events(events)

    if player.color not in state.teams:
        return "You are not in the game yet!"

    team = state.teams[player.color]

    msg = f"📊 {team.name} ({team.color})\n"
    msg += f"💣 Bombs: {team.bombs}\n"

    ships_placed = sum(team.placed_ship_types.values())
    total_ships = sum(SHIP_COUNTS.values())
    msg += f"🚢 Ships: {ships_placed}/{total_ships}\n"

    sunk = len(team.get_sunk_ships())
    msg += f"💥 Sunk ships: {sunk}"

    img = render_private_board(team)
    img_bytes = boards_to_bytes(img)
    await send_photo(context, chat_id, img_bytes, caption=msg)

    public_img = render_all_public_boards(state)
    public_bytes = boards_to_bytes(public_img)
    await send_photo(context, chat_id, public_bytes, caption="All teams' public boards")

    return None


async def handle_location(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    latitude: float,
    longitude: float,
    code: Optional[str],
):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role.value != "gamemaster":
        return "Only game masters can add locations!"

    number = await get_next_location_number(db)
    location_code = code.upper() if code else generate_code()

    await create_location(db, number, latitude, longitude, location_code)

    await add_event(
        db,
        EventType.LOCATION_ADDED,
        {
            "number": number,
            "latitude": latitude,
            "longitude": longitude,
            "code": location_code,
        },
        player.id,
    )

    return f"Location {number} added!\nCode: {location_code}\nhttps://maps.google.com/?q={latitude},{longitude}"


async def handle_locations_list(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    locations = await get_all_locations(db)

    if not locations:
        return "No locations have been added yet."

    msg = "📍 Locations:\n"
    for loc in locations:
        msg += (
            f"{loc.number}. https://maps.google.com/?q={loc.latitude},{loc.longitude}\n"
        )

    return msg


async def handle_register_gm(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    existing_player = await get_player_by_chat(db, chat_id)
    if existing_player:
        if existing_player.role.value == "gamemaster":
            return "You are already registered as a game master!"
        return "You are already registered as a team!"

    player = await create_player(db, "GameMaster", "gm", chat_id, Role.GAMEMASTER)

    return "You are now registered as a game master!"


async def handle_create_locations(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    count: int,
    latitude: float,
    longitude: float,
    radius_km: float = 2.0,
):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can create locations!"

    import random
    import string

    created = []
    from app.models import get_next_location_number

    for i in range(count):
        lat_offset = random.uniform(-radius_km / 111, radius_km / 111)
        lon_offset = random.uniform(
            -radius_km / (111 * math.cos(latitude * math.pi / 180)),
            radius_km / (111 * math.cos(latitude * math.pi / 180)),
        )

        lat = latitude + lat_offset
        lon = longitude + lon_offset

        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))

        number = await get_next_location_number(db)
        await create_location(db, number, lat, lon, code)

        await add_event(
            db,
            EventType.LOCATION_ADDED,
            {"number": number, "latitude": lat, "longitude": lon, "code": code},
        )

        created.append(f"{number}. {code} - https://maps.google.com/?q={lat},{lon}")

    msg = f"✅ Created {count} locations around ({latitude}, {longitude}):\n"
    msg += "\n".join(created)

    return msg


async def handle_start_game(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can start the game!"

    from app.models import get_or_create_game_settings, update_game_settings
    from app.database import GameStatus

    settings = await get_or_create_game_settings(db)

    if settings.status == GameStatus.STARTED:
        return "The game has already started!"

    if settings.status == GameStatus.ENDED:
        return "The game has ended! Use /resetgame to start a new game."

    await update_game_settings(db, status=GameStatus.STARTED)

    return "🎮 The game has started! Teams can now use bombs and redeem codes!"


async def handle_reset_game(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can reset the game!"

    from app.models import update_game_settings
    from app.database import GameStatus

    await update_game_settings(db, status=GameStatus.WAITING, started_at=None)

    return "🔄 The game has been reset! Teams can now join again."
