# main.py
import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    JobQueue
)
import asyncio
from datetime import time
import random

# === 🔑 Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === 🌐 Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN не задан!")
    exit(1)

try:
    CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
except (TypeError, ValueError):
    logger.critical("❌ CHANNEL_ID должен быть числом")
    exit(1)

PORT = int(os.getenv("PORT", 8080))

# === 📸 Контент для автопостинга ===
POSTS = [
    {
        "photo": "https://i.ibb.co/6YpZ1fL/roller-blinds.jpg",
        "caption": "✨ Рулонные шторы в интерьере\n— Ткань: блэкаут\n— Установка: 1 час\n— Цена: от 2990 ₽\nЗаказ: @manager"
    },
    {
        "photo": "https://i.ibb.co/8XK0z1q/vertical-blinds.jpg",
        "caption": "🔥 Вертикальные жалюзи — идеальны для больших окон\n— Цвет: серый\n— Цена: от 3500 ₽\n@manager"
    },
    {
        "photo": "https://i.ibb.co/0jT0fZk/roman-shades.jpg",
        "caption": "💫 Римские шторы — элегантность и уют\n— Материал: лён\n— Цена: от 4200 ₽\n@manager"
    }
]

TIPS = [
    "💡 <b>Совет эксперта:</b>\nКак выбрать блэкаут-ткань?\n— Плотность: от 300 г/м²",
    "🔥 <b>Лайфхак:</b>\nЧистите жалюзи влажной губкой с каплей средства для посуды"
]

PROMOS = [
    "🎉 <b>Акция недели!</b>\nСкидка 20% на вертикальные жалюзи!\nТолько до воскресенья."
]

# === 🕐 Функции автопостинга ===
async def daily_morning(context: ContextTypes.DEFAULT_TYPE):
    text = random.choice(TIPS)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        logger.info("☀️ Утренний совет отправлен")
    except Exception as e:
        logger.error(f"❌ Ошибка утром: {e}")

async def daily_afternoon(context: ContextTypes.DEFAULT_TYPE):
    post = random.choice(POSTS)
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=post["photo"].strip(),  # Убираем лишние пробелы
            caption=post["caption"]
        )
        logger.info("🌤️ Дневной пост отправлен")
    except Exception as e:
        logger.error(f"❌ Ошибка днём: {e}")

# === 🚀 Глобальный Application (создаётся один раз) ===
application = None

async def setup_application():
    global application
    application = Application.builder().token(BOT_TOKEN).build()

    # Настраиваем задачи
    job_queue = application.job_queue
    job_queue.run_daily(daily_morning, time(hour=10, minute=0))    # 10:00
    job_queue.run_daily(daily_afternoon, time(hour=15, minute=0))  # 15:00

    # Устанавливаем вебхук один раз
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}.onrender.com/webhook/{BOT_TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Вебхук установлен: {webhook_url}")

    # Запускаем job_queue
    await job_queue.start()

# === 🏠 Flask приложение ===
app = Flask(__name__)

@app.route('/')
def health():
    return '<h1>✅ SMM Bot is Running</h1>', 200

@app.route('/webhook/<string:token>', methods=['POST'])
def webhook(token):
    if token != BOT_TOKEN:
        logger.warning(f"❌ Неверный токен: {token}")
        return 'Unauthorized', 401

    if not request.is_json:
        logger.warning("❌ Получен не-JSON запрос")
        return 'Bad Request', 400

    try:
        # Обрабатываем обновление
        update = Update.de_json(request.get_json(), application.bot)
        asyncio.run(application.process_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"❌ Ошибка в вебхуке: {e}")
        return 'Internal Server Error', 500

# === 🔥 Запуск сервера и бота ===
if __name__ == '__main__':
    # Запускаем настройку бота
    asyncio.run(setup_application())
    logger.info("✅ Бот запущен и ожидает вебхуки...")

    # Запускаем Flask
    app.run(host="0.0.0.0", port=PORT)
