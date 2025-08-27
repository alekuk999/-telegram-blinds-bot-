# main.py
import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram import Update

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаём FastAPI-приложение
app = FastAPI()

# Глобальная переменная для хранения экземпляра бота
bot_application = None

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! 🤖\n"
        "Я бот для управления жалюзи!\n"
        "Используй команды:\n"
        "/open — открыть жалюзи\n"
        "/close — закрыть жалюзи\n"
        "/status — узнать состояние"
    )
    logger.info(f"Пользователь {update.effective_user.id} вызвал /start")


async def open_blinds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда: открыть жалюзи"""
    await update.message.reply_text("✅ Жалюзи открыты")
    logger.info(f"Жалюзи открыты пользователем {update.effective_user.id}")


async def close_blinds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда: закрыть жалюзи"""
    await update.message.reply_text("❌ Жалюзи закрыты")
    logger.info(f"Жалюзи закрыты пользователем {update.effective_user.id}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда: текущее состояние"""
    await update.message.reply_text("📊 Состояние: жалюзи открыты")
    logger.info(f"Пользователь {update.effective_user.id} запросил состояние")


# --- Инициализация бота ---
@app.on_event("startup")
async def startup():
    """Выполняется при запуске сервера"""
    global bot_application

    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.error("🛑 ОШИБКА: Переменная окружения TELEGRAM_TOKEN не установлена!")
        raise RuntimeError("TELEGRAM_TOKEN обязательна для работы бота!")

    # Создаём Application
    bot_application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    bot_application.add_handler(CommandHandler("start", start))
    bot_application.add_handler(CommandHandler("open", open_blinds))
    bot_application.add_handler(CommandHandler("close", close_blinds))
    bot_application.add_handler(CommandHandler("status", status))

    # Можно добавить обработку текста, если нужно
    # bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("✅ Бот успешно инициализирован и готов принимать сообщения")


# --- Вебхук для Telegram ---
@app.post("/webhook/{token}")
async def webhook(token: str, request: Request):
    """
    Точка входа для вебхука от Telegram
    Проверяет токен и передаёт обновление боту
    """
    global bot_application

    expected_token = os.getenv("TELEGRAM_TOKEN")
    if not expected_token:
        logger.error("🛑 TELEGRAM_TOKEN не установлен!")
        return PlainTextResponse("Сервер не настроен", status_code=500)

    # Проверка токена в URL
    if token != expected_token:
        logger.warning(f"❌ Неверный токен в вебхуке: {token}")
        return PlainTextResponse("Неверный токен", status_code=403)

    # Проверка, инициализирован ли бот
    if bot_application is None:
        logger.error("❌ bot_application не инициализирован")
        return PlainTextResponse("Бот не готов", status_code=500)

    try:
        # Получаем JSON из запроса
        json_data = await request.json()
        update = Update.de_json(json_data, bot_application.bot)

        # Передаём обновление в диспетчер
        await bot_application.process_update(update)
        logger.info("📩 Обновление обработано")
        return PlainTextResponse("OK", status_code=200)

    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")
        return PlainTextResponse("Ошибка", status_code=500)


# --- Health-check ---
@app.get("/")
def health():
    """Простая проверка, что сервис работает"""
    return {
        "status": "работает",
        "bot": "готов" if bot_application else "не готов",
        "message": "Telegram бот для управления жалюзи"
    }


@app.get("/health")
def health_detailed():
    """Подробная проверка состояния"""
    return {
        "status": "healthy",
        "bot_initialized": bot_application is not None,
        "telegram_token_set": bool(os.getenv("TELEGRAM_TOKEN")),
    }
