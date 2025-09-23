# main.py
import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Проверка переменных окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в окружении!")
if not CHANNEL_ID:
    raise ValueError("❌ CHANNEL_ID не задан в окружении!")

logger.info("✅ Переменные окружения загружены:")
logger.info(f"BOT_TOKEN: {'✅ задан' if BOT_TOKEN else '❌ не задан'}")
logger.info(f"CHANNEL_ID: {'✅ задан' if CHANNEL_ID else '❌ не задан'}")
logger.info(f"YANDEX_API_KEY: {'✅ задан' if YANDEX_API_KEY else '❌ не задан'}")
logger.info(f"FOLDER_ID: {'✅ задан' if FOLDER_ID else '❌ не задан'}")

# === Команды бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я бот для канала про жалюзи.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/tip /promo /work /gpt [тема]")

# === Запуск Telegram-бота ===
async def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    logger.info("🚀 Telegram-бот запущен через polling!")
    await app.start()
    await app.updater.start_polling()
    await app.idle()

# === HTTP-сервер для Timeweb ===
def run_http_se
