
from flask import Flask, request
from telegram import Update
from telegram.ext import Application
import os
import logging
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === 🔑 Токен из переменной окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN не задан в переменных окружения!")
    exit(1)

# === 🌐 Порт и Flask приложение ===
PORT = int(os.getenv("PORT", 8080))
app = Flask(__name__)

# === 🧩 Создаём Application (пока без запуска) ===
application = None

# === ✅ Маршрут для вебхука (исправленный) ===
@app.route('/webhook/<string:token>', methods=['POST'])
def webhook(token):
    # Проверяем токен
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
        # Обрабатываем обновление
        update = Update.de_json(request.get_json(), application.bot)
        asyncio.run(application.process_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"❌ Ошибка обработки обновления: {e}")
        return 'Internal Server Error', 500

# === 🏠 Health check ===
@app.route('/')
def health():
    return '<h1>✅ Blinds Bot is Running</h1>', 200

# === 🚀 Запуск бота ===
async def setup_bot():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавьте обработчики
    # application.add_handler(...)

    # Устанавливаем вебхук
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}.onrender.com/webhook/{BOT_TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Вебхук установлен: {webhook_url}")

# === 🔥 Запуск ===
if __name__ == '__main__':
    asyncio.run(setup_bot())
    app.run(host="0.0.0.0", port=PORT)
