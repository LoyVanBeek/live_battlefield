import logging

logger = logging.getLogger(__name__)

from app.game.ships import (
    SHIP_SIZES,
    SHIP_COUNTS,
    VALID_SHIP_TYPES,
    VALID_DIRECTIONS,
    parse_coordinate,
    coordinate_to_string,
)
from app.game.state import GameState, BombResult, TEAM_COLORS
from app.game.board import (
    render_all_public_boards,
    render_private_board,
    boards_to_bytes,
)
from app.database import Role
from app.models import (
    get_player_by_chat,
    get_player_by_id,
    get_player_by_color_in_game,
    create_player,
    get_all_teams_in_game,
    get_all_players_in_game,
    get_all_game_masters,
    get_game_events,
    get_location_by_number,
    create_location,
    get_next_location_number,
    get_game_locations,
    update_game_status,
    create_team_token,
    delete_team_token,
)
from app.events import (
    EventType,
    TeamJoinedEvent,
    ShipPlacedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
    BombsAddedEvent,
    TeamResetEvent,
    GameStartedEvent,
    save_event,
)
from app.bot.helpers import send_message, send_photo
from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional
from datetime import datetime, timezone
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
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    logger.info(f"handle_join: chat_id={chat_id} team_name={team_name}")

    try:
        existing_player = await get_player_by_chat(db, chat_id)
        logger.info(f"handle_join: existing_player={existing_player}")
        if existing_player:
            await db.delete(existing_player)
            await db.commit()

        from app.models import get_all_games
        games = await get_all_games(db)
        if not games:
            return "No active game found"
        game_id = games[0].id
        game = games[0]

        if game.status.value == "started":
            return "The game has already started! No new teams can join."
        if game.status.value == "ended":
            return "The game has ended! Use /resetgame to start a new game."

        events = await get_game_events(db, game_id)
        state = GameState.from_events(events)

        if state.is_team_name_taken(team_name):
            return f"Team name '{team_name}' is already taken!"

        colors_in_game = set(state.teams.keys())

        from app.models import get_all_players_in_game

        all_players = await get_all_players_in_game(db, game_id)
        colors_in_db = {p.color for p in all_players}

        taken_colors = colors_in_game | colors_in_db

        color = None
        for c in TEAM_COLORS:
            if c not in taken_colors:
                color = c
                break

        if not color:
            return "No more colors available! The game is full."

        logger.info(f"handle_join: creating player team={team_name} color={color}")
        player = await create_player(db, game_id=game_id, name=team_name, color=color, chat_id=chat_id)
        logger.info(f"handle_join: player created id={player.id}")

        from app.events.models import generate_team_token
        from app.models import create_team_token

        token = generate_team_token()
        event = TeamJoinedEvent(name=team_name, color=color, chat_id=chat_id, bombs=3, token=token)
        await save_event(db, event, game_id=game_id)
        await create_team_token(db, game_id, token, color)
        logger.info(f"handle_join: event saved")

        return f"Welcome {team_name}! You are the {color} team.\nYou have 0 bombs to start. Visit locations to earn bombs!"
    except Exception as e:
        logger.exception(
            f"handle_join: ERROR chat_id={chat_id} team_name={team_name}: {e}"
        )
        return "Something went wrong! Please try again or contact a Game Master."


async def handle_leave(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    try:
        existing_player = await get_player_by_chat(db, chat_id)
        if not existing_player:
            return "You are not in the game yet!"

        if existing_player.role == Role.GAMEMASTER:
            return "Game Masters cannot leave the game. Contact another GM to reset."

        game_id = existing_player.game_id
        from app.models import get_game
        game = await get_game(db, game_id)
        if game and game.status.value == "started":
            return "Cannot leave - the game has already started!"

        await db.delete(existing_player)
        await db.commit()

        return "You have left the game. Use /join <team_name> to rejoin."
    except Exception as e:
        print(f"Error in handle_leave: {e}")
        return "Something went wrong! Please try again or contact a Game Master."


async def handle_place(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ship_type: str,
    coord: str,
    direction: str,
):
    if update.effective_chat is None:
        return
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

    game_id = player.game_id
    events = await get_game_events(db, game_id)
    state = GameState.from_events(events)

    if player.color not in state.teams:
        return "You are not in the game yet!"

    team = state.teams[player.color]

    if not team.can_place_ship(ship_type):
        return f"You've already placed all your {ship_type} ships!"

    success, _ = team.place_ship(ship_type, row, col, direction)
    if not success:
        return "Cannot place ship there! Check boundaries and that ships don't touch."

    event = ShipPlacedEvent(
        color=player.color,
        ship_type=ship_type,
        row=row,
        col=col,
        direction=direction,
    )
    await save_event(db, event, game_id=game_id)

    img = render_private_board(team)
    img_bytes = boards_to_bytes(img)

    await send_photo(
        context,
        chat_id,
        img_bytes,
        caption=f"Ship placed! Ships left: {SHIP_COUNTS[ship_type] - team.placed_ship_types.get(ship_type, 0)}",
    )

    return None


async def handle_place_all(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat is None:
        return

    from app.services.ship_placement import place_all_ships_game_scoped

    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    game_id = player.game_id
    from app.models import get_game
    game = await get_game(db, game_id)
    if game and game.status.value == "started":
        return "Cannot place ships - the game has already started!"

    success, message = await place_all_ships_game_scoped(db, str(game_id), player.color)

    if not success:
        return message

    return f"🚢 {message}"


async def handle_bomb(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_color: str,
    coord: str,
):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    try:
        row, col = parse_coordinate(coord)
    except ValueError as e:
        return str(e)

    game_id = player.game_id
    events = await get_game_events(db, game_id)
    state = GameState.from_events(events)

    if state.status.value != "started":
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
    result, ship, new_target = target.receive_bomb(row, col, player.color)
    state.teams[target_color] = new_target

    event = BombThrownEvent(
        attacker_color=player.color,
        target_color=target_color,
        row=row,
        col=col,
        result=result.value,
    )
    await save_event(db, event, game_id=game_id)

    target_player = await get_player_by_color_in_game(db, game_id, target_color)
    if target_player and target_player.chat_id:
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
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    game_id = player.game_id
    location = await get_location_by_number(db, game_id, location_number)
    if not location:
        return f"Location {location_number} does not exist!"

    events = await get_game_events(db, game_id)
    state = GameState.from_events(events)

    if state.status.value != "started":
        return (
            "The game hasn't started yet! Wait for all ships and locations to be ready."
        )

    if player.color not in state.teams:
        return "You are not in the game yet!"

    team = state.teams[player.color]

    if location.code.upper() != code.upper():
        return "Invalid code! Please check the code at the location."

    events = await get_game_events(db, game_id)
    for event in events:
        if event.event_type == EventType.CODE_REDEEMED:
            payload = event.payload
            if (
                payload.get("color") == player.color
                and payload.get("location_number") == location_number
            ):
                return "You've already visited this location!"

    bomb_value = location.bomb_value
    team.bombs += bomb_value

    event = CodeRedeemedEvent(
        color=player.color,
        location_number=location_number,
        code=code.upper(),
        success=True,
        bombs_earned=bomb_value,
    )
    await save_event(db, event, game_id=game_id)

    return f"Correct! +{bomb_value} bomb(s) added. You now have {team.bombs} bombs."


async def handle_overview(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    game_id = player.game_id
    events = await get_game_events(db, game_id)
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
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role.value != "gamemaster":
        return "Only game masters can add locations!"

    game_id = player.game_id
    number = await get_next_location_number(db, game_id)
    location_code = code.upper() if code else generate_code()

    await create_location(db, game_id, number, latitude, longitude, location_code)

    event = LocationAddedEvent(
        number=number,
        latitude=latitude,
        longitude=longitude,
        code=location_code,
    )
    await save_event(db, event, game_id=game_id)

    return f"Location {number} added!\nCode: {location_code}\nhttps://maps.google.com/?q={latitude},{longitude}"


async def handle_locations_list(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to join the game first! Use /join <team name>"

    game_id = player.game_id
    locations = await get_game_locations(db, game_id)

    if not locations:
        return "No locations have been added yet."

    num_locations = len(locations)
    default_bomb_value = max(1, 100 // num_locations)

    for loc in locations:
        try:
            await context.bot.send_location(
                chat_id=chat_id,
                latitude=loc.latitude,
                longitude=loc.longitude,
            )
        except Exception as e:
            print(f"Error sending location: {e}")

    msg = f"📍 {len(locations)} Locations (Worth {default_bomb_value} bombs each by default):\n"
    for loc in locations:
        bomb_val = loc.bomb_value if loc.bomb_value else default_bomb_value
        if bomb_val != default_bomb_value:
            msg += f"  • Location {loc.number}: {bomb_val} bombs\n"

    if (
        msg
        == f"📍 {len(locations)} Locations (Worth {default_bomb_value} bombs each by default):\n"
    ):
        msg = f"📍 {len(locations)} Locations (Worth {default_bomb_value} bombs each)"
    else:
        msg += "\n💣 GM can override with /setlocationbombs"

    return msg


async def handle_register_gm(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    existing_player = await get_player_by_chat(db, chat_id)
    if existing_player:
        if existing_player.role.value == "gamemaster":
            return "You are already registered as a game master!"
        existing_player.role = Role.GAMEMASTER
        await db.commit()
        return (
            "You are now also registered as a game master! You can now use GM commands."
        )

    from app.models import get_all_games
    games = await get_all_games(db)
    if not games:
        return "No active game found"
    game_id = games[0].id

    player = await create_player(db, game_id=game_id, name="GameMaster", color="gm", chat_id=chat_id, role=Role.GAMEMASTER)

    return "You are now registered as a game master!"


async def handle_add_ai(
    db, update: Update, context: ContextTypes.DEFAULT_TYPE, color: str, name: str | None = None
):
    if update.effective_chat is None:
        return

    from app.database import Role

    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can add AI players!"

    if not name:
        name = f"{color.title()} AI"

    from app.game.state import TEAM_COLORS

    if color not in TEAM_COLORS:
        return f"Invalid color! Choose from: {', '.join(TEAM_COLORS)}"

    game_id = player.game_id

    all_players_in_game = await get_all_players_in_game(db, game_id)
    existing_colors = [p.color for p in all_players_in_game]

    if color in existing_colors:
        return f"Team {color} already exists! Use /removeai {color} first, or choose a different color."

    from app.services.ai_player import add_ai_player, get_ai_player

    existing_ai = get_ai_player(game_id, color)
    if existing_ai:
        return f"AI player for {color} already exists!"

    new_player = await create_player(db, game_id=game_id, name=name, color=color, chat_id=None, role=Role.AI)

    ai = add_ai_player(game_id, color, name)

    from app.services.ship_placement import place_all_ships_game_scoped

    await place_all_ships_game_scoped(db, str(game_id), color)

    from app.events.models import generate_team_token

    token = generate_team_token()
    event = TeamJoinedEvent(name=name, color=color, chat_id=0, bombs=3, token=token)
    await save_event(db, event, game_id=game_id)
    await create_team_token(db, game_id, token, color)

    return f"🤖 Added AI player '{name}' ({color})! Ships auto-placed. Use /aistatus to see all AI players."


async def handle_remove_ai(
    db, update: Update, context: ContextTypes.DEFAULT_TYPE, color: str
):
    if update.effective_chat is None:
        return

    from app.database import Role

    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can remove AI players!"

    game_id = player.game_id

    from app.services.ai_player import remove_ai_player, get_ai_player

    ai = get_ai_player(game_id, color)
    if not ai:
        return f"No AI player with color {color}!"
    player_to_remove = await get_player_by_color_in_game(db, game_id, color)
    if player_to_remove:
        await db.delete(player_to_remove)
        await db.commit()

    await delete_team_token(db, game_id, color)
    remove_ai_player(game_id, color)

    return f"🤖 Removed AI player {color}!"


async def handle_ai_status(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    player = await get_player_by_chat(db, chat_id)
    if not player or player.role != Role.GAMEMASTER:
        return "Only game masters can check AI status!"
    game_id = player.game_id
    from app.services.ai_player import get_all_ai_players, is_all_ai_paused

    all_ais = get_all_ai_players(game_id)

    if not all_ais:
        return "No AI players currently active. Use /addai <color> to add one."

    status = "🤖 AI Players:\n\n"
    global_paused = is_all_ai_paused(game_id)
    if global_paused:
        status += "⏸️ All AI players are PAUSED\n\n"

    for color, ai in all_ais.items():
        paused = "⏸️" if ai.is_paused else "▶️"
        status += f"{paused} {ai.name} ({ai.color})\n"

    return status


async def handle_create_locations(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    count: int,
    latitude: float,
    longitude: float,
    radius_km: float = 2.0,
):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can create locations!"

    game_id = player.game_id
    existing_locations = await get_game_locations(db, game_id)
    if len(existing_locations) + count > 100:
        return f"Cannot create {count} locations! Would exceed 100 maximum. Current: {len(existing_locations)}"

    import random
    import string

    created = []

    total_after = len(existing_locations) + count
    default_bomb_value = max(1, 100 // total_after)

    for loc in existing_locations:
        loc.bomb_value = default_bomb_value

    for i in range(count):
        lat_offset = random.uniform(-radius_km / 111, radius_km / 111)
        lon_offset = random.uniform(
            -radius_km / (111 * math.cos(latitude * math.pi / 180)),
            radius_km / (111 * math.cos(latitude * math.pi / 180)),
        )

        lat = latitude + lat_offset
        lon = longitude + lon_offset

        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))

        number = await get_next_location_number(db, game_id)

        from app.database import Location

        new_location = Location(
            game_id=game_id,
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
        await save_event(db, event, game_id=game_id)

        created.append(f"{number}. {code} - Worth {default_bomb_value} bombs")

    await db.commit()

    msg = f"✅ Created {count} locations around ({latitude}, {longitude}). Each worth {default_bomb_value} bombs (Total: 100):\n"
    msg += "\n".join(created)
    msg += (
        f"\n\nTotal locations: {total_after}. Bombs per location: {default_bomb_value}"
    )

    return msg


async def handle_set_location_bombs(
    db,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    location_number: int,
    bomb_count: int,
):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can set location bomb values!"

    game_id = player.game_id
    location = await get_location_by_number(db, game_id, location_number)
    if not location:
        return f"Location {location_number} does not exist!"

    if bomb_count < 1:
        return "Bomb count must be at least 1!"

    location.bomb_value = bomb_count
    await db.commit()

    return f"✅ Location {location_number} now worth {bomb_count} bombs!"


async def handle_start_game(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can start the game!"

    game_id = player.game_id

    from app.database import GameStatus
    from app.models import get_game

    game = await get_game(db, game_id)
    if not game:
        return "Game not found!"
    if game.status == GameStatus.STARTED:
        return "The game has already started!"
    if game.status == GameStatus.ENDED:
        return "The game has ended! Use /resetgame to start a new game."

    await update_game_status(db, game_id, GameStatus.STARTED, started_at=datetime.now(timezone.utc))

    event = GameStartedEvent()
    await save_event(db, event, game_id=game_id)

    return "🎮 The game has started! Teams can now use bombs and redeem codes!"


async def handle_reset_game(db, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    player = await get_player_by_chat(db, chat_id)
    if not player:
        return "You need to register as a game master first!"

    if player.role != Role.GAMEMASTER:
        return "Only game masters can reset the game!"

    game_id = player.game_id

    from app.database import GameStatus

    await update_game_status(db, game_id, GameStatus.WAITING, started_at=None)

    all_gms = await get_all_game_masters(db)
    for gm in all_gms:
        await db.delete(gm)
    await db.commit()

    return "🔄 The game has been reset! All Game Masters have been removed. Use /registergm to become a GM again."
