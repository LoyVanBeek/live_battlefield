from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_keyboard():
    keyboard = [
        [InlineKeyboardButton("Join Game", callback_data="join")],
        [InlineKeyboardButton("View Locations", callback_data="locations")],
    ]
    return InlineKeyboardMarkup(keyboard)
