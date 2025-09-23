# blinds_bot.py
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
from datetime import time, timezone
import random
import requests

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в .env")
if not CHANNEL_ID:
    raise ValueError("❌ CHANNEL_ID не задан в .env")

# === Контент для канала ===

TIPS = [
    "💡 <b>Совет эксперта:</b>\nКак выбрать блэкаут-ткань?\n— Плотность: от 300 г/м²\n— Цвет: тёмные оттенки лучше блокируют свет",
    "🔥 <b>Лайфхак:</b>\nЧистите жалюзи влажной губкой с каплей средства для посуды — легко и безопасно!",
    "✅ <b>Идея для маленьких окон:</b>\nРулонные шторы «день-ночь» визуально увеличат пространство!"
]

PROMOS = [
    "🎉 <b>Акция недели!</b>\nСкидка 20% на вертикальные жалюзи!\nТолько до воскресенья.\n👉 Напишите «Хочу скидку» — пришлём замерщика!",
    "🚀 <b>Установка за 1 день!</b>\nЗакажите до пятницы — установим в субботу!\nЦена как на сайте + подарок!"
]

WORKS = [
    {
        "photo": "https://img.freepik.com/free-photo/modern-living-room-interior-design_1268-16720.jpg",
        "caption": "✨ Рулонные шторы в интерьере кухни\n— Ткань: блэкаут\n— Установка: 1 час\n— Цена: от 2990 ₽\nЗаказать: @manager"
    },
    {
        "photo": "https://img.freepik.com/free-photo/vertical-blinds-window_1268-17953.jpg",
        "caption": "🛠 Вертикальные жалюзи в офисе\n— Цвет: серый металлик\n— Управление: цепочкой\n— Гарантия: 2 года"
    }
]

# === Генерация текста через Yandex GPT ===
async def generate_post_text(topic: str) -> str:
    if not YANDEX_API_KEY or not FOLDER_ID:
        return f"⚠️ Невозможно сгенерировать пост: не заданы YANDEX_API_KEY или FOLDER_ID.\nТема: {topic}"

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"""
Ты — маркетолог в компании по продаже жалюзи и штор.
Напиши пост для Telegram-канала на тему: "{topic}".
Стиль: дружелюбный, экспертный, с эмодзи и хэштегами.
Добавь призыв к действию: "Заказать замер → @manager".
Объём: 3-5 строк.
    """

    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 800
        },
        "messages": [
            {"role": "system", "text": "Ты — автор Telegram-канала про жалюзи. Пиши кратко, ярко, с пользой."},
            {"role": "user", "text": prompt}
        ]
    }

    try:
        # Используем синхронный requests — в продакшене лучше aiohttp, но для простоты оставим
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            text = result['result']['alternatives'][0]['message']['text']
            return text[:1020] + "..." if len(text) > 1024 else text
        else:
            logger.error(f"Ошибка Yandex GPT: {response.text}")
            return f"❌ Ошибка генерации: {response.status_code}"
    except Exception as e:
        logger.error(f"Исключение при генерации: {e}")
        return f"⚠️ Не удалось сгенерировать пост: {str(e)}"

# === Обработчики команд ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для канала про жалюзи.\n\n"
        "<b>Команды:</b>\n"
        "/tip — совет эксперта\n"
        "/promo — акция недели\n"
        "/work — фото работы\n"
        "/gpt [тема] — сгенерировать пост через ИИ\n"
        "/help — помощь",
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 <b>Доступные команды:</b>\n"
        "/tip — совет по уходу или выбору\n"
        "/promo — акция\n"
        "/work — фото установки\n"
        "/gpt Тема — генерация поста через Yandex GPT\n\n"
        f"Бот публикует в канал: {CHANNEL_ID}",
        parse_mode="HTML"
    )

async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = random.choice(TIPS)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        await update.message.reply_text("✅ Совет опубликован в канале!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка публикации совета: {e}")

async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = random.choice(PROMOS)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        await update.message.reply_text("✅ Акция опубликована!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка публикации акции: {e}")

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = random.choice(WORKS)
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=item["photo"],
            caption=item["caption"]
        )
        await update.message.reply_text("✅ Фото работы опубликовано!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка публикации фото: {e}")

async def gpt_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 Укажите тему, например:\n/gpt Как выбрать рулонные шторы?")
        return

    topic = " ".join(context.args)
    await update.message.reply_text("🧠 Генерирую пост через Yandex GPT...")

    generated_text = await generate_post_text(topic)

    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=generated_text, parse_mode="HTML")
        await update.message.reply_text("✅ Пост опубликован в канале!")
    except Exception as e:
        error_msg = f"❌ Ошибка публикации: {str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(f"Ошибка публикации сгенерированного поста: {e}")

# === Ежедневные посты (по расписанию) ===
async def daily_morning(context: ContextTypes.DEFAULT_TYPE):
    tip_text = random.choice(TIPS)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=tip_text, parse_mode="HTML")
        logger.info("✅ Утренний пост опубликован")
    except Exception as e:
        logger.error(f"Ошибка утреннего поста: {e}")

async def daily_afternoon(context: ContextTypes.DEFAULT_TYPE):
    item = random.choice(WORKS)
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=item["photo"],
            caption=item["caption"]
        )
        logger.info("✅ Дневной пост с фото опубликован")
    except Exception as e:
        logger.error(f"Ошибка дневного поста: {e}")

# === Запуск бота ===
def main():
    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tip", tip))
    application.add_handler(CommandHandler("promo", promo))
    application.add_handler(CommandHandler("work", work))
    application.add_handler(CommandHandler("gpt", gpt_post))

    # Настраиваем расписание
    # ⚠️ Важно: указываем timezone, иначе будет UTC
    job_queue = application.job_queue

    # Публикации по МСК (UTC+3)
    job_queue.run_daily(
        daily_morning,
        time=time(hour=10, minute=0, tzinfo=timezone.utc)  # 10:00 UTC = 13:00 МСК
    )
    job_queue.run_daily(
        daily_afternoon,
        time=time(hour=12, minute=0, tzinfo=timezone.utc)  # 12:00 UTC = 15:00 МСК
    )

    # ИЛИ если хотите по локальному времени сервера (если сервер в МСК):
    # job_queue.run_daily(daily_morning, time=time(hour=10, minute=0))
    # job_queue.run_daily(daily_afternoon, time=time(hour=15, minute=0))

    logger.info("🚀 Бот запущен! Публикации по расписанию: 13:00 и 15:00 МСК (UTC+3)")

    # Запускаем polling
    application.run_polling()

if __name__ == "__main__":
    main()
