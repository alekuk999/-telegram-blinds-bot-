import os
from dotenv import load_dotenv
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHANNEL_URL = os.getenv("TELEGRAM_CHANNEL")
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER")
CATALOG_IMAGE_URL = "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"  # Готовое фото — не трогать!


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[DEBUG] Бот получил команду /start")

    keyboard = [
        [InlineKeyboardButton("📚 Каталог", callback_data='catalog')],
        [InlineKeyboardButton("🛒 Заказать", callback_data='order')],
        [InlineKeyboardButton("📞 Контакты", callback_data='contacts')],
        [InlineKeyboardButton("🔗 Перейти в канал", url=TELEGRAM_CHANNEL_URL)],
        [InlineKeyboardButton("💬 Написать в WhatsApp", url=f"https://wa.me/{WHATSAPP_NUMBER}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Добро пожаловать в магазин рулонных штор и жалюзи Астрахань!\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )


# Обработка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'catalog':
        logger.info("[DEBUG] Пользователь нажал 'Каталог'")
        await query.edit_message_text(text="📦 Вот наш актуальный каталог:")
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=CATALOG_IMAGE_URL,
            caption="✨ Рулонные шторы и жалюзи от производителя.\nЦены, цвета, размеры — всё здесь!"
        )

    elif query.data == 'order':
        logger.info("[DEBUG] Пользователь нажал 'Заказать'")
        await query.edit_message_text(
            text="📝 Чтобы сделать заказ, отправьте мне:\n\n"
                 "1. ✏️ Размеры окна (ширина × высота в см)\n"
                 "2. 🎨 Цвет или текстура (например: белый матовый, дуб светлый)\n"
                 "3. 📍 Адрес доставки (город, улица, дом, квартира)\n\n"
                 "Я перезвоню вам в течение 15 минут и подтвержу стоимость!"
        )

    elif query.data == 'contacts':
        logger.info("[DEBUG] Пользователь нажал 'Контакты'")
        await query.edit_message_text(
            text="📍 *Контактная информация*:\n\n"
                 "📞 Телефон: +7 (927) 822-09-06\n"
                 "⏰ Режим работы: 9:00 — 19:00 (ежедневно)\n"
                 "🏠 Адрес: г. Астрахань, ул. Ленина, д. 10, офис 5\n\n"
                 "📲 Также пишите в WhatsApp: 👇\n"
                 f"https://wa.me/{WHATSAPP_NUMBER}"
        )

    else:
        logger.warning(f"[DEBUG] Неизвестный callback: {query.data}")
        await query.edit_message_text(text="❌ Неизвестная команда. Попробуйте снова.")


# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[DEBUG] Пользователь вызвал /help")
    await update.message.reply_text(
        "📌 Я — бот магазина рулонных штор и жалюзи в Астрахани.\n\n"
        "Используйте кнопки ниже для выбора действий:\n\n"
        "• *Каталог* — посмотреть товары и цены\n"
        "• *Заказать* — оформить заявку на замер и доставку\n"
        "• *Контакты* — узнать адрес и телефон\n"
        "• *Канал* — подписаться на акции и новинки\n"
        "• *WhatsApp* — написать нам прямо сейчас\n\n"
        "Всё просто — выбери нужную кнопку!"
    )


# Запуск бота
def main():
    logger.info("🚀 Запуск бота...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ Бот запущен и готов к работе!")
    app.run_polling()


if __name__ == '__main__':
    main()
