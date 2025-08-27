# main.py
import os
import logging
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    JobQueue
)
import asyncio
from datetime import time
import random

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === 🔑 Токен и ID канала из переменных окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN не задан!")
    exit(1)

try:
    CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
except (TypeError, ValueError):
    logger.critical("❌ CHANNEL_ID должен быть числом")
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

WORKS = [
    {
        "photo": "https://i.ibb.co/6YpZ1fL/roller-blinds.jpg",
        "caption": "✨ Рулонные шторы в интерьере\n— Установка: 1 час\n— Цена: от 2990 ₽\nЗаказ: @manager"
    }
]

# === 🔘 Клавиатура ===
KEYBOARD = [
    ["💡 Совет", "🎉 Акция"],
    ["🖼 Фото", "📢 Пост"]
]
reply_markup = ReplyKeyboardMarkup(KEYBOARD, resize_keyboard=True)

# === 🧩 Глобальные переменные ===
application = None

# === 📝 Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие:", reply_markup=reply_markup)

async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = random.choice(TIPS)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        await update.message.reply_text("✅ Совет опубликован!")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await update.message.reply_text("❌ Не удалось опубликовать.")

async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = random.choice(PROMOS)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        await update.message.reply_text("✅ Акция опубликована!")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await update.message.reply_text("❌ Не удалось опубликовать.")

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = random.choice(WORKS)
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=item["photo"],
            caption=item["caption"]
        )
        await update.message.reply_text("✅ Фото опубликовано!")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await update.message.reply_text("❌ Не удалось опубликовать.")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажите текст: /post Новинка — шторы день-ночь!")
        return
    text = " ".join(context.args)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
        await update.message.reply_text("✅ Текст опубликован!")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await update.message.reply_text("❌ Не удалось опубликовать.")

# === 🕐 Автопостинг ===
async def daily_morning(context: ContextTypes.DEFAULT_TYPE):
    text = random.choice(TIPS)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        logger.info("☀️ Утренний пост отправлен")
    except Exception as e:
        logger.error(f"❌ Ошибка утром: {e}")

async def daily_afternoon(context: ContextTypes.DEFAULT_TYPE):
    item = random.choice(WORKS)
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=item["photo"],
            caption=item["caption"]
        )
        logger.info("🌤️ Дневной пост отправлен")
    except Exception as e:
        logger.error(f"❌ Ошибка днём: {e}")

# === 🔘 Обработчик кнопок ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "💡 Совет":
        await tip(update, context)
    elif text == "🎉 Акция":
        await promo(update, context)
    elif text == "🖼 Фото":
        await work(update, context)
    elif text == "📢 Пост":
        await post(update, context)
    else:
        await update.message.reply_text("Выбери действие:", reply_markup=reply_markup)

# === ✅ Маршрут для вебхука ===
@app.route('/webhook/<string:token>', methods=['POST'])
def webhook(token):
    if token != BOT_TOKEN:
        logger.warning(f"❌ Неверный токен: {token}")
        return 'Unauthorized', 401

    if not request.is_json:
        logger.warning("❌ Получен не-JSON запрос")
        return 'Bad Request', 400

    global application
    if application is None:
        logger.error("❌ application не инициализирован")
        return 'Server Error', 500

    try:
        update = Update.de_json(request.get_json(), application.bot)
        asyncio.run(application.process_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return 'Internal Server Error', 500

# === 🏠 Health check ===
@app.route('/')
def health():
    return '<h1>✅ SMM Bot is Running</h1>', 200

# === 🚀 Запуск бота ===
async def setup_bot():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    job_queue = application.job_queue

    # Планирование задач
    job_queue.run_daily(daily_morning, time(hour=10, minute=0))
    job_queue.run_daily(daily_afternoon, time(hour=15, minute=0))

    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tip", tip))
    application.add_handler(CommandHandler("promo", promo))
    application.add_handler(CommandHandler("work", work))
    application.add_handler(CommandHandler("post", post))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Устанавливаем вебхук
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}.onrender.com/webhook/{BOT_TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Вебхук установлен: {webhook_url}")

    job_queue.start()

# === 🔥 Запуск ===
if __name__ == '__main__':
    asyncio.run(setup_bot())
    app.run(host="0.0.0.0", port=PORT)
