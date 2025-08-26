
# main.py
import os
import logging
import requests
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext,
    JobQueue
)
from datetime import time
from flask import Flask, request
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === 🔑 Переменные окружения ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.error("❌ BOT_TOKEN не задан!")
    exit(1)

try:
    CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
except (TypeError, ValueError):
    logger.error("❌ CHANNEL_ID должен быть числом")
    exit(1)

# === 🌐 Порт и Flask ===
PORT = int(os.getenv("PORT", 8080))
app = Flask(__name__)

# === 📸 Контент ===
TIPS = [
    "💡 <b>Совет эксперта:</b>\nКак выбрать блэкаут-ткань?\n— Плотность: от 300 г/м²",
    "🔥 <b>Лайфхак:</b>\nЧистите жалюзи влажной губкой с каплей средства для посуды"
]

PROMOS = [
    "🎉 <b>Акция недели!</b>\nСкидка 20% на вертикальные жалюзи!\nТолько до воскресенья."
]

WORKS_STATIC = [
    {
        "photo": "https://i.ibb.co/6YpZ1fL/roller-blinds.jpg",
        "caption": "✨ Рулонные шторы в интерьере\n— Установка: 1 час\n— Цена: от 2990 ₽\nЗаказ: @manager"
    }
]

# Динамический пул фото
WORKS_DYNAMIC = []

# === 🔘 Клавиатура ===
KEYBOARD = [
    ["💡 Совет", "🎉 Акция"],
    ["🖼 Фото", "📢 Пост"]
]
reply_markup = ReplyKeyboardMarkup(KEYBOARD, resize_keyboard=True)

# === 🧩 Глобальные переменные ===
application = None

# === 🔍 Автообновление: Unsplash API ===
def fetch_blinds_photos():
    global WORKS_DYNAMIC
    UNSPLASH_KEY = os.getenv("UNSPLASH_KEY")
    if not UNSPLASH_KEY:
        return

    headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
    params = {
        "query": "blinds interior roller shades",
        "per_page": 10,
        "orientation": "landscape"
    }

    try:
        response = requests.get("https://api.unsplash.com/search/photos", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        new_photos = []
        for item in data.get("results", []):
            photo_url = item["urls"]["regular"]
            author = item["user"]["name"]
            caption = (
                f"🖼 Интерьер с жалюзи\n"
                f"📸 Автор: {author}\n"
                f"🔗 Через Unsplash\n"
                f"Заказ: @manager"
            )
            new_photos.append({"photo": photo_url, "caption": caption})

        WORKS_DYNAMIC = (WORKS_DYNAMIC + new_photos)[-50:]
        logger.info(f"✅ Найдено {len(new_photos)} фото с Unsplash")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

async def fetch_blinds_job(context: CallbackContext):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, fetch_blinds_photos)

# === 📝 Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие:", reply_markup=reply_markup)

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_works = WORKS_STATIC + WORKS_DYNAMIC
    if not all_works:
        await update.message.reply_text("Нет фото для публикации")
        return
    item = random.choice(all_works)
    try:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=item["photo"], caption=item["caption"])
        await update.message.reply_text("✅ Фото опубликовано!")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

# ... остальные команды: tip, promo, post

# === ✅ Вебхук ===
@app.route('/webhook/<string:token>', methods=['POST'])
def webhook(token):
    if token != TOKEN:
        return 'Unauthorized', 401
    if request.is_json:
        update = Update.de_json(request.get_json(), application.bot)
        asyncio.run(application.update_queue.put(update))
        return 'OK', 200
    return 'Bad Request', 400

@app.route('/')
def health():
    return '<h1>✅ SMM Bot is Running</h1>', 200

# === 🚀 Запуск ===
async def setup_bot():
    global application
    application = Application.builder().token(TOKEN).build()
    job_queue = application.job_queue

    job_queue.run_daily(fetch_blinds_job, time(hour=9, minute=0))
    job_queue.run_daily(daily_morning, time(hour=10, minute=0))
    job_queue.run_daily(daily_afternoon, time(hour=15, minute=0))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("work", work))
    # ... другие обработчики

    await application.bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}.onrender.com/webhook/{TOKEN}")
    logger.info("✅ Вебхук установлен")
    job_queue.start()

if __name__ == '__main__':
    asyncio.run(setup_bot())
    app.run(host="0.0.0.0", port=PORT)
