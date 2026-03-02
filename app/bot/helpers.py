from telegram import Update
from telegram.ext import ContextTypes


async def send_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        print(f"Error sending message: {e}")


async def send_photo(context: ContextTypes.DEFAULT_TYPE, chat_id: int, photo_bytes: bytes, caption: str = ""):
    try:
        from io import BytesIO
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=BytesIO(photo_bytes),
            caption=caption
        )
    except Exception as e:
        print(f"Error sending photo: {e}")
