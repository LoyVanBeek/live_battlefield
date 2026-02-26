from fastapi import FastAPI
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import threading

from app.config import settings
from app.database import init_db, async_session_maker
from app.api.routes import app as fastapi_app
from app.bot.handlers import (
    handle_join,
    handle_place,
    handle_bomb,
    handle_code,
    handle_overview,
    handle_location,
    handle_locations_list,
    handle_register_gm,
    handle_create_locations,
    handle_set_location_bombs,
    handle_start_game,
    handle_reset_game,
)


async def safe_reply(update: Update, text: str):
    """Safely reply to an update, handling cases where message might be None"""
    if update and update.message:
        await update.message.reply_text(text)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(
        update,
        "Welcome to Live Battlefield!\n\n"
        "Commands:\n"
        "/join <team_name> - Join the game\n"
        "/registergm - Register as game master\n"
        "/place <ship_type> <coordinate> <direction> - Place a ship\n"
        "/bomb <team_color> <coordinate> - Throw a bomb\n"
        "/code <location_number> <code> - Redeem a code\n"
        "/overview - View your boards\n"
        "/locations - View all locations\n"
        "/startgame - Start the game (GM)\n"
        "/resetgame - Reset the game (GM)\n"
        "/help - Show this help message\n\n"
        "Ship types: airplane_carrier, battleship, torpedo_hunter, patrol_boat\n"
        "Coordinates: A1-J10\n"
        "Directions: horizontal, vertical\n\n"
        "Example: /place battleship B2 horizontal",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🎮 Live Battlefield - Commands

📝 For Players:
/join <team_name> - Join the game
/place <ship_type> <coordinate> <direction> - Place a ship
/bomb <team_color> <coordinate> - Throw a bomb
/code <location_number> <code> - Redeem a location code
/overview - View your boards
/locations - View all locations

👮 For Game Masters:
/registergm - Register as game master
/create_locations <count> <lat> <lon> [radius] - Create locations
/startgame - Start the game
/resetgame - Reset the game

📋 Ship types: airplane_carrier (6), battleship (4), torpedo_hunter (3), patrol_boat (2)
📍 Coordinates: A1-J10 (A-J columns, 1-10 rows)
↔️ Directions: horizontal, vertical

Example: /place battleship B2 horizontal"""
    await safe_reply(update, help_text)


async def join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /join <team_name>")
        return

    team_name = " ".join(context.args)
    async with async_session_maker() as db:
        result = await handle_join(db, update, context, team_name)
        if result:
            await update.message.reply_text(result)


async def place_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /place <ship_type> <coordinate> <direction>"
        )
        return

    ship_type = context.args[0].lower()
    coord = context.args[1].upper()
    direction = context.args[2].lower()

    async with async_session_maker() as db:
        result = await handle_place(db, update, context, ship_type, coord, direction)
        if result:
            await safe_reply(update, result)


async def bomb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await safe_reply(update, "Usage: /bomb <team_color> <coordinate>")
        return

    target_color = context.args[0].lower()
    coord = context.args[1].upper()

    async with async_session_maker() as db:
        result = await handle_bomb(db, update, context, target_color, coord)
        if result:
            await safe_reply(update, result)


async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await safe_reply(update, "Usage: /code <location_number> <code>")
        return

    try:
        location_number = int(context.args[0])
    except ValueError:
        await safe_reply(update, "Location number must be a number")
        return

    code = context.args[1]

    async with async_session_maker() as db:
        result = await handle_code(db, update, context, location_number, code)
        await safe_reply(update, result)


async def overview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_maker() as db:
        await handle_overview(db, update, context)


async def locations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_maker() as db:
        result = await handle_locations_list(db, update, context)
        await safe_reply(update, result)


async def register_gm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_maker() as db:
        result = await handle_register_gm(db, update, context)
        await safe_reply(update, result)


async def create_locations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await safe_reply(
            update,
            "Usage: /create_locations <count> <latitude> <longitude> [radius_km]",
        )
        return

    try:
        count = int(context.args[0])
        latitude = float(context.args[1])
        longitude = float(context.args[2])
        radius = float(context.args[3]) if len(context.args) > 3 else 2.0
    except ValueError:
        await safe_reply(
            update,
            "Invalid parameters. Usage: /create_locations <count> <latitude> <longitude> [radius_km]",
        )
        return

    async with async_session_maker() as db:
        result = await handle_create_locations(
            db, update, context, count, latitude, longitude, radius
        )
        await safe_reply(update, result)


async def set_location_bombs_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if len(context.args) < 2:
        await safe_reply(
            update, "Usage: /setlocationbombs <location_number> <bomb_count>"
        )
        return

    try:
        location_number = int(context.args[0])
        bomb_count = int(context.args[1])
    except ValueError:
        await safe_reply(
            update,
            "Invalid parameters. Usage: /setlocationbombs <location_number> <bomb_count>",
        )
        return

    async with async_session_maker() as db:
        result = await handle_set_location_bombs(
            db, update, context, location_number, bomb_count
        )
        await safe_reply(update, result)


async def start_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_maker() as db:
        result = await handle_start_game(db, update, context)
        await safe_reply(update, result)


async def reset_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_maker() as db:
        result = await handle_reset_game(db, update, context)
        await safe_reply(update, result)


async def location_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        return

    lat = update.message.location.latitude
    lon = update.message.location.longitude
    code = update.message.text if update.message.text else None

    async with async_session_maker() as db:
        result = await handle_location(db, update, context, lat, lon, code)
        await safe_reply(update, result)


async def post_init(application: Application):
    await init_db()


def run_bot():
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("join", join_handler))
    app.add_handler(CommandHandler("place", place_handler))
    app.add_handler(CommandHandler("bomb", bomb_handler))
    app.add_handler(CommandHandler("code", code_handler))
    app.add_handler(CommandHandler("overview", overview_handler))
    app.add_handler(CommandHandler("locations", locations_handler))
    app.add_handler(CommandHandler("registergm", register_gm_handler))
    app.add_handler(CommandHandler("create_locations", create_locations_handler))
    app.add_handler(CommandHandler("setlocationbombs", set_location_bombs_handler))
    app.add_handler(CommandHandler("startgame", start_game_handler))
    app.add_handler(CommandHandler("resetgame", reset_game_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_message_handler))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def run_server():
    import uvicorn

    uvicorn.run(fastapi_app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    import sys
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "bot":
        run_bot()
    elif len(sys.argv) > 1 and sys.argv[1] == "server":
        run_server()
    else:
        from concurrent.futures import ThreadPoolExecutor
        import threading
        import asyncio

        executor = ThreadPoolExecutor(max_workers=1)

        def run_server_block():
            import uvicorn

            uvicorn.run(
                fastapi_app, host=settings.host, port=settings.port, log_level="info"
            )

        server_thread = threading.Thread(target=run_server_block, daemon=True)
        server_thread.start()

        print("Server started, starting bot...")
        run_bot()
