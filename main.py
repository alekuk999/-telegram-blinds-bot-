import os
import threading
import time
import logging
from datetime import datetime
import sqlite3
import hashlib
import random
import requests
import re
import telebot
from telebot import types

# === Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в окружении!")

CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002137931247")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
MANAGER_CHAT_ID = 7126605143

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
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
            category TEXT,
            image_url TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            phone TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("✅ [DB] База данных инициализирована.")

# === Добавление тестовых данных ===
def add_sample_data():
    logger.info("📚 [DB] Проверка и добавление тестовых данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ("Рулонные шторы день-ночь", "✨ Чередование прозрачных и плотных полос — регулируйте свет без подъёма шторы.", "Рулонные шторы", "https://i.imgur.com/5XJkR9l.jpg"),
            ("Рулонные шторы блэкаут", "🌙 100% затемнение — идеально для спальни и домашнего кинотеатра.", "Рулонные шторы", "https://i.imgur.com/L3GzF9P.jpg"),
            ("Горизонтальные жалюзи алюминиевые", "🔧 Алюминиевые ламели 25 мм — лёгкие, прочные, не ржавеют.", "Горизонтальные жалюзи", "https://i.imgur.com/8KfR2sT.jpg"),
            ("Вертикальные жалюзи тканевые", "🌿 Плотный полиэстер — не выгорает, поглощает шум, создаёт уют.", "Вертикальные жалюзи", "https://i.imgur.com/rDkLmN7.jpg"),
        ]
        cursor.executemany("INSERT INTO products (name, description, category, image_url) VALUES (?, ?, ?, ?)", products)
        logger.info("✅ [DB] Тестовые товары добавлены.")

    conn.commit()
    conn.close()

# === Сохранение заявки ===
def save_call_request(user_id, first_name, phone_number):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_id, user_name, phone, status)
        VALUES (?, ?, ?, ?)
    ''', (user_id, first_name, phone_number, "pending"))
    conn.commit()
    conn.close()

def notify_manager(user_name, phone_number):
    try:
        bot.send_message(
            MANAGER_CHAT_ID,
            f"🔔 <b>Новая заявка на звонок!</b>\n\n👤 Имя: {user_name}\n📱 Телефон: <code>{phone_number}</code>",
            parse_mode='HTML'
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
        "Authorization": f"Api-Key {YANDEX_API_KEY}"  # ← ИСПРАВЛЕНО!
    }
    prompt = f"""
Ты — маркетолог компании «Рулонные шторы и жалюзи в Астрахани».
Создай цепляющий пост для Telegram-канала.

Товар: {product_name}
Описание: {product_description}

Требования:
- Заголовок ≤ 50 символов
- Текст ≤ 200 символов, с эмодзи
- Хэштеги: #Астрахань #ЖалюзиАстрахань и один по теме
- Призыв: "Напишите в WhatsApp или Telegram!"

Ответь строго в JSON:
{{
    "title": "...",
    "content": "...",
    "hashtags": ["...", "...", "..."]
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
            logger.error("❌ Не удалось извлечь JSON")
            return None, None
    except Exception as e:
        logger.error(f"❌ Ошибка Yandex GPT: {e}")
        return None, None

# === Автопостинг ===
def auto_generate_and_publish_post():
    logger.info("🔍 Выбираем товар из базы...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, image_url FROM products ORDER BY RANDOM() LIMIT 1")
    product = cursor.fetchone()
    conn.close()

    if not product:
        logger.warning("❌ Нет товаров")
        return

    name, desc, image_url = product
    title, content = generate_post_with_yandex_gpt(name, desc)

    if not title or not content:
        logger.error("❌ Не удалось сгенерировать пост")
        return

    try:
        caption = f"📌 <b>{title}</b>\n\n{content}"
        if image_url and image_url.startswith("http"):
            bot.send_photo(CHANNEL_ID, image_url, caption=caption, parse_mode='HTML')
        else:
            bot.send_message(CHANNEL_ID, caption, parse_mode='HTML')
        logger.info(f"✅ Пост опубликован: {title}")
    except Exception as e:
        logger.error(f"💥 Ошибка публикации: {e}")

def send_scheduled_posts():
    logger.info("⏱️ [AUTOPOST] Задача автопостинга запущена")
    last_day = None
    while True:
        now = datetime.utcnow()
        if now.hour == 10 and now.minute == 0:  # 10:00 UTC = 13:00 МСК
            today = now.date()
            if last_day != today:
                auto_generate_and_publish_post()
                last_day = today
        time.sleep(60)

# === Команды бота ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Каталог", "🛒 Заказать")
    markup.add("📞 Контакты", "💬 WhatsApp")
    bot.reply_to(message, "👇 Выберите раздел:", reply_markup=markup)

@bot.message_handler(commands=['testpost'])
def test_post(message):
    auto_generate_and_publish_post()
    bot.reply_to(message, "✅ Тестовый пост отправлен в канал!")

@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def show_contacts(message):
    bot.reply_to(
        message,
        "📍 <b>Контактная информация</b>:\n\n"
        "📞 Телефон: +7 (937) 822-29-06\n"
        "💬 WhatsApp: <a href='https://wa.me/79378222906'>Написать</a>\n"
        "✉️ Telegram: <a href='https://t.me/astra_jalyzi30'>Написать менеджеру</a>\n"
        "⏰ Режим работы: 9:00 — 19:00\n"
        "🏠 Адрес: г. Астрахань, ул. Ленина, д. 10, офис 5",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda m: m.text == "💬 WhatsApp")
def open_whatsapp(message):
    bot.reply_to(
        message,
        "💬 Напишите нам в WhatsApp:\n\nhttps://wa.me/79378222906",
        reply_markup=types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("📲 Открыть чат", url="https://wa.me/79378222906")]
        ])
    )

# === Каталог ===
@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    text = "✨ <b>Выберите категорию:</b>"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🧵 Рулонные шторы", callback_data="category_Рулонные шторы"))
    markup.add(types.InlineKeyboardButton("🪟 Горизонтальные жалюзи", callback_data="category_Горизонтальные жалюзи"))
    markup.add(types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call"))
    bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    category = call.data.split('_', 1)[1]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, image_url FROM products WHERE category = ?", (category,))
    products = cursor.fetchall()
    conn.close()

    if not products:
        bot.send_message(call.message.chat.id, f"📦 В категории <b>{category}</b> пока нет товаров.", parse_mode='HTML')
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
                bot.send_message(call.message.chat.id, f"<b>{name}</b>\n{desc}", parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")

# === Заказ звонка ===
@bot.callback_query_handler(func=lambda call: call.data == "request_call")
def request_call_handler(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        "📞 Отправьте номер телефона — перезвоним в течение 5 минут!",
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

    save_call_request(message.from_user.id, user_name, phone)
    notify_manager(user_name, phone)

    bot.send_message(
        message.chat.id,
        f"✅ Спасибо, {user_name}!\nМы получили ваш номер: <code>{phone}</code>\n📞 Менеджер перезвонит вам в течение 5 минут!",
        parse_mode='HTML',
        reply_markup=types.ReplyKeyboardRemove()
    )

# === Запуск ===
if __name__ == '__main__':
    init_db()
    add_sample_data()
    threading.Thread(target=send_scheduled_posts, daemon=True).start()
    logger.info("🚀 Бот запущен через polling!")
    bot.polling(none_stop=True, interval=0, timeout=20)
