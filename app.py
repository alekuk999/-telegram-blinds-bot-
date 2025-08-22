# app.py
import os
import logging
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# === Переменные окружения (установите в Render) ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Например: https://your-app.onrender.com
PORT = int(os.getenv("PORT", 8000))

if not TOKEN:
    raise ValueError("Не установлен TELEGRAM_BOT_TOKEN в переменных окружения!")
if not WEBHOOK_URL:
    raise ValueError("Не установлен WEBHOOK_URL в переменных окружения!")

# === Flask приложение ===
app = Flask(__name__)

# === Обработчики команд ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение с кнопками"""
    keyboard = [
        [InlineKeyboardButton("🎨 Каталог штор", callback_data="catalog")],
        [InlineKeyboardButton("📞 Заказать замер", url="https://t.me/yourmanager")],
        [InlineKeyboardButton("🖼 Наши работы", callback_data="portfolio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "👋 Здравствуйте!\n"
            "Мы делаем стильные **рулонные шторы и жалюзи** на заказ.\n"
            "Быстрая установка, гарантия, скидки!\n\n"
            "Выберите, что вас интересует:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            "👋 Здравствуйте!\n"
            "Мы делаем стильные **рулонные шторы и жалюзи** на заказ.\n"
            "Быстрая установка, гарантия, скидки!\n\n"
            "Выберите, что вас интересует:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    if query.data == "catalog":
        text = (
            "📦 **Каталог продукции**:\n\n"
            "• Рулонные шторы «День-ночь» — от 1500 ₽/м²\n"
            "• Вертикальные жалюзи — от 1200 ₽/м²\n"
            "• Горизонтальные алюминиевые — от 1000 ₽/м²\n"
            "• Тканевые роллеты — от 1800 ₽/м²\n\n"
            "📏 Замер — бесплатный!\n"
            "📞 Напишите менеджеру: @yourmanager"
        )
        await query.edit_message_text(text=text, parse_mode="Markdown")

    elif query.data == "portfolio":
        text = (
            "📸 **Наши последние работы**:\n\n"
            "Посмотрите реальные фото установок:\n"
            "👉 https://t.me/your_portfolio_channel\n\n"
            "Подписывайтесь и вдохновляйтесь!"
        )
        await query.edit_message_text(text=text, parse_mode="Markdown")


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /contact"""
    await update.message.reply_text(
        "📞 Свяжитесь с нами:\n"
        "Менеджер: @yourmanager\n"
        "Работаем ежедневно с 9:00 до 21:00\n"
        "Замер — бесплатно в черте города."
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любые текстовые сообщения"""
    await update.message.reply_text(
        "Спасибо за сообщение! 🙏\n"
        "Чтобы выбрать товар или заказать замер — нажмите /start\n"
        "Или напишите напрямую: @yourmanager"
    )


# === Настройка бота при старте ===
async def setup_application(application: Application):
    """Добавляем хендлеры и устанавливаем вебхук"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("contact", contact))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Устанавливаем вебхук
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Вебхук установлен: {webhook_url}")


# === Flask маршруты ===
@app.route("/")
def index():
    return "<h1>Бот для жалюзи запущен ✅</h1>", 200


@app.route("/webhook", methods=["POST"])
async def webhook():
    """Приём обновлений от Telegram"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Empty data"}), 400

        # Преобразуем в объект Update
        update = Update.de_json(data, bot_app.bot)

        # Передаём обновление в бота
        await bot_app.update_queue.put(update)

        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.error(f"❌ Ошибка в вебхуке: {e}")
        return jsonify({"error": str(e)}), 500


# === Глобальный экземпляр бота ===
bot_app = None


@app.before_first_request
async def initialize():
    """Выполняется при первом запросе (Render запускает с /)"""
    global bot_app
    if bot_app is None:
        bot_app = (
            Application.builder()
            .token(TOKEN)
            .updater(None)  # Отключаем встроенный polling
            .build()
        )
        await setup_application(bot_app)
        logger.info("🤖 Бот инициализирован и готов к работе")


# === Точка входа (для Render) ===
if __name__ == "__main__":
    import asyncio

    # Для локального теста (не используется на Render)
    async def run():
        global bot_app
        bot_app = Application.builder().token(TOKEN).build()
        await setup_application(bot_app)
        await bot_app.run_polling()

    # Раскомментируйте, если тестируете локально
    # asyncio.run(run())
