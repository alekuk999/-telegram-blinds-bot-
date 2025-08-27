# bot.py
import os
from telegram.ext import Application

application = None

async def init_bot():
    global application
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set")
    
    application = Application.builder().token(BOT_TOKEN).build()
    # Добавьте обработчики и job_queue здесь
    return application
