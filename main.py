# main.py
import os
import threading
import time
import logging
from datetime import datetime
import sqlite3
import hashlib
import random
import requests
import json
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в окружении!")

CHANNEL_ID = os.getenv("CHANNEL_ID", "@astra_jaluzi")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
MANAGER_CHAT_ID = 7126605143  # Убедитесь, что это число (int)

# === Инициализация бота ===
import telebot
from telebot import types

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# === Путь к БД ===
DB_PATH = "blinds_bot.db"

# === Инициализация базы данных ===
def init_db():
    logger.info("🔧 [DB] Инициализация базы данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL,
            category TEXT,
            image_url TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            user_name TEXT,
            phone TEXT,
            address TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            is_from_user BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS smm_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            image_url TEXT,
            category TEXT,
            scheduled_time TIMESTAMP,
            is_published BOOLEAN DEFAULT 0,
            weekday INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("✅ [DB] База данных инициализирована.")

# === Добавление тестовых товаров ===
def add_sample_data():
    logger.info("📚 [DB] Проверка и добавление тестовых данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            (
                "Рулонные шторы день-ночь",
                "✨ *Идеально для спальни и гостиной!*\n\n"
                "• *Функция*: Чередование прозрачных и плотных полос — регулируйте свет без подъёма шторы.\n"
                "• *Материал*: Полиэстер с пропиткой — не выгорает, не впитывает запахи.\n"
                "• *Цвета*: Белый, бежевый, серый, графит.\n"
                "• *Размеры*: Под заказ — от 40 см до 300 см в ширину.",
                0.0,
                "Рулонные шторы",
                "https://img.freepik.com/free-photo/modern-living-room-interior-design_1268-16720.jpg"
            ),
            (
                "Горизонтальные жалюзи алюминиевые",
                "🔧 *Классика, проверенная временем!*\n\n"
                "• *Материал*: Алюминиевые ламели 25 мм — лёгкие, прочные, не ржавеют.\n"
                "• *Цвета*: Белый, серебро, золото, дерево, металлик — более 20 оттенков.\n"
                "• *Управление*: Поворот ламелей на 180° — регулируйте свет и приватность.\n"
                "• *Применение*: Кухня, ванная, балкон — не боятся влаги и пара.",
                0.0,
                "Горизонтальные жалюзи",
                "https://img.freepik.com/free-photo/vertical-blinds-window_1268-17953.jpg"
            ),
            (
                "Вертикальные жалюзи тканевые",
                "🌿 *Элегантность и уют в вашем доме!*\n\n"
                "• *Ткань*: Плотный полиэстер — не выгорает, не впитывает запахи, поглощает шум.\n"
                "• *Управление*: Плавный поворот и сдвиг в сторону — легко регулировать освещение.\n"
                "• *Цвета*: Пастельные тона — бежевый, серый, молочный, лаванда.\n"
                "• *Применение*: Гостиная, спальня, офис — создают ощущение простора.",
                0.0,
                "Вертикальные жалюзи",
                "https://img.freepik.com/free-photo/vertical-blinds-living-room_1268-18021.jpg"
            )
        ]
        cursor.executemany("INSERT INTO products (name, description, price, category, image_url) VALUES (?, ?, ?, ?, ?)", products)
        logger.info("✅ [DB] Тестовые товары добавлены.")

    cursor.execute("SELECT COUNT(*) FROM smm_content")
    if cursor.fetchone()[0] == 0:
        logger.info("ℹ️ [DB] Таблица smm_content пуста — посты будут генерироваться через Яндекс GPT.")

    conn.commit()
    conn.close()

# === Вспомогательные функции ===
def save_user(user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
                   (user.id, user.username, user.first_name, user.last_name))
    conn.commit()
    conn.close()

def save_message(user_id, text, is_from_user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (user_id, message, is_from_user) VALUES (?, ?, ?)',
                   (user_id, text, is_from_user))
    conn.commit()
    conn.close()

def notify_manager(user_name, phone):
    try:
        bot.send_message(
            MANAGER_CHAT_ID,
            f"🔔 *Новая заявка на звонок!*\n\n👤 Имя: {user_name}\n📱 Телефон: `{phone}`\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка уведомления менеджера: {e}")

# === Генерация поста через Yandex GPT ===
def generate_post_with_yandex_gpt(product_name, product_description):
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        logger.error("❌ YANDEX_API_KEY или YANDEX_FOLDER_ID не заданы")
        return None, None

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {YANDEX_API_KEY}"  # ← КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ!
    }
    prompt = f"""
Ты — маркетолог интернет-магазина жалюзи и рулонных штор в Астрахани.
Создай цепляющий пост для Telegram-канала на основе описания товара.

Товар: {product_name}
Описание: {product_description}

Пост должен включать:
- Яркий заголовок (не более 50 символов)
- Основной текст (не более 200 символов, с эмодзи)
- 3 релевантных хэштега
- Призыв к действию: "Напишите в WhatsApp или Telegram!"

Ответь строго в формате JSON:
{{
    "title": "заголовок",
    "content": "текст поста",
    "hashtags": ["#хэштег1", "#хэштег2", "#хэштег3"]
}}
"""

    data = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 1000
        },
        "messages": [{"role": "user", "text": prompt}]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        text = result['result']['alternatives'][0]['message']['text']

        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            post_data = json.loads(json_match.group())
            full_content = f"{post_data['content']}\n\n{' '.join(post_data['hashtags'])}"
            return post_data['title'], full_content
        else:
            logger.error("❌ Не удалось извлечь JSON из ответа")
            return None, None
    except Exception as e:
        logger.error(f"❌ Ошибка Yandex GPT: {e}")
        return None, None

# === Автопостинг в 10:00 UTC (13:00 МСК) ===
def auto_generate_and_publish_post():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, image_url FROM products ORDER BY RANDOM() LIMIT 1")
    product = cursor.fetchone()
    conn.close()

    if not product:
        logger.warning("❌ Нет товаров в базе")
        return

    name, desc, image_url = product
    title, content = generate_post_with_yandex_gpt(name, desc)

    if not title or not content:
        logger.error("❌ Не удалось сгенерировать пост")
        return

    try:
        caption = f"📌 *{title}*\n\n{content}"
        if image_url.startswith("http"):
            bot.send_photo(CHANNEL_ID, image_url, caption=caption, parse_mode='Markdown')
        else:
            with open(image_url, 'rb') as f:
                bot.send_photo(CHANNEL_ID, f, caption=caption, parse_mode='Markdown')
        logger.info(f"✅ Пост опубликован: {title}")
    except Exception as e:
        logger.error(f"❌ Ошибка публикации: {e}")

def send_scheduled_posts():
    logger.info("⏱️ [AUTOPOST] Задача автопостинга запущена")
    last_auto_post_day = None
    while True:
        try:
            now = datetime.utcnow()
            if now.hour == 10 and now.minute == 0:
                today = now.date()
                if last_auto_post_day != today:
                    auto_generate_and_publish_post()
                    last_auto_post_day = today
            time.sleep(60)
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле автопостинга: {e}")
            time.sleep(60)

# === Обработчики команд ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user(message.from_user)
    save_message(message.from_user.id, message.text, True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Каталог", "🛒 Заказать")
    markup.add("🔗 Канал", "📞 Контакты")
    markup.add("💬 WhatsApp", "ℹ️ Помощь")
    bot.reply_to(message, "👇 Выберите нужный раздел:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    text = "✨ *Выберите категорию товаров:*"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🧵 Рулонные шторы", callback_data="category_Рулонные шторы"),
        types.InlineKeyboardButton("🪟 Горизонтальные жалюзи", callback_data="category_Горизонтальные жалюзи"),
        types.InlineKeyboardButton("🚪 Вертикальные жалюзи", callback_data="category_Вертикальные жалюзи"),
        types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/79378222906"),
        types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call")
    )
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    category = call.data.split('_', 1)[1]
    bot.answer_callback_query(call.id)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, image_url FROM products WHERE category = ?", (category,))
    products = cursor.fetchall()
    conn.close()

    if not products:
        bot.send_message(call.message.chat.id, f"📦 В категории *{category}* пока нет товаров.", parse_mode='Markdown')
        return

    for name, desc, image_url in products:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call"),
            types.InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/79378222906")
        )
        try:
            if image_url.startswith("http"):
                bot.send_photo(call.message.chat.id, image_url, caption=f"<b>{name}</b>\n{desc}", parse_mode='HTML', reply_markup=markup)
            else:
                with open(image_url, 'rb') as f:
                    bot.send_photo(call.message.chat.id, f, caption=f"<b>{name}</b>\n{desc}", parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            bot.send_message(call.message.chat.id, f"❌ Не удалось загрузить фото для '{name}'.")

@bot.callback_query_handler(func=lambda call: call.data == "request_call")
def request_call_handler(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        "📞 *Пожалуйста, отправьте ваш номер телефона*, и мы перезвоним вам в течение 5 минут!\n\n"
        "📱 Вы можете:\n• Нажать кнопку *«Отправить номер»* ниже\n• Или ввести номер вручную (например: `+79271234567`)",
        parse_mode='Markdown',
        reply_markup=types.ReplyKeyboardMarkup(
            row_width=1, resize_keyboard=True, one_time_keyboard=True
        ).add(types.KeyboardButton("📲 Отправить мой номер", request_contact=True))
    )
    bot.register_next_step_handler(msg, process_phone_number, call.from_user.first_name)

def process_phone_number(message, user_name):
    phone = message.contact.phone_number if message.contact else message.text.strip()
    if not phone:
        bot.send_message(message.chat.id, "❌ Не удалось получить номер.")
        return

    notify_manager(user_name, phone)
    bot.send_message(
        message.chat.id,
        f"✅ Спасибо, {user_name}!\n\nМы получили ваш номер: `{phone}`\n📞 Менеджер перезвонит вам в течение 5 минут!",
        parse_mode='Markdown',
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def show_contacts(message):
    bot.reply_to(
        message,
        "📍 *Контактная информация*:\n\n"
        "📞 Телефон: +7 (937) 822-29-06\n"
        "💬 WhatsApp: [Написать](https://wa.me/79378222906)\n"
        "✉️ Telegram: [Написать менеджеру](https://t.me/astra_jalyzi30)\n"
        "⏰ Режим работы: 9:00 — 19:00 (ежедневно)\n"
        "🏠 Адрес: г. Астрахань, ул. Ленина, д. 10, офис 5",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "💬 WhatsApp")
def open_whatsapp(message):
    bot.reply_to(
        message,
        "💬 Напишите нам прямо сейчас в WhatsApp:\n\nhttps://wa.me/79378222906",
        reply_markup=types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("📲 Открыть чат", url="https://wa.me/79378222906")]
        ])
    )

@bot.message_handler(func=lambda m: m.text == "🔗 Канал")
def open_channel(message):
    bot.reply_to(message, f"📢 Подписывайтесь на наш канал:\n\n{CHANNEL_ID}")

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def send_help(message):
    bot.reply_to(
        message,
        "📌 *Доступные функции бота*:\n\n"
        "• *Каталог* — посмотреть товары\n"
        "• *Заказать* — оставить заявку\n"
        "• *Контакты* — узнать адрес и телефон\n"
        "• *Канал* — подписаться на акции\n"
        "• *WhatsApp* — написать мгновенно\n\n"
        "💡 Все запросы обрабатываются вручную!"
    )

# === Главный запуск ===
if __name__ == '__main__':
    init_db()
    add_sample_data()

    # Запуск автопостинга в фоне
    threading.Thread(target=send_scheduled_posts, daemon=True).start()

    logger.info("🚀 Бот запущен через polling!")
    bot.polling(none_stop=True, interval=0, timeout=20)
