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

# === Отключаем лишние логи ===
logging.getLogger("gunicorn").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from flask import Flask, request, jsonify
import telebot
from telebot import types

# === Настройки приложения ===
app = Flask(__name__)

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не установлена!")

CHANNEL_ID = os.getenv("CHANNEL_ID", "@astra_jaluzi")
PORT = int(os.getenv("PORT", 8000))

# === Настройки Yandex Cloud ===
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

# === Путь к базе данных ===
DB_PATH = "blinds_bot.db"

# === Ваш Chat ID для уведомлений ===
MANAGER_CHAT_ID = 7126605143

# === Флаг для отслеживания инициализации ===
_INITIALIZED = False

# === Инициализация базы данных ===
def init_db():
    print("🔧 [DB] Инициализация базы данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT
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
    print("✅ [DB] База данных инициализирована.")

# === Добавление тестовых данных ===
def add_sample_data():
    print("📚 [DB] Проверка и добавление тестовых данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ("Рулонные шторы день-ночь", "Чередование прозрачных и плотных полос — регулируйте свет без подъёма шторы.", "Рулонные шторы"),
            ("Рулонные шторы блэкаут", "100% затемнение — идеально для спальни и домашнего кинотеатра.", "Рулонные шторы"),
            ("Горизонтальные жалюзи алюминиевые", "Алюминиевые ламели 25 мм — лёгкие, прочные, не ржавеют.", "Горизонтальные жалюзи"),
            ("Вертикальные жалюзи тканевые", "Плотный полиэстер — не выгорает, поглощает шум, создаёт уют.", "Вертикальные жалюзи"),
            ("Жалюзи плиссе", "Гармошка — идеальны для мансард, эркеров и нестандартных окон.", "Жалюзи плиссе"),
            ("Деревянные жалюзи", "Натуральная древесина — дуб, орех. Служат 15+ лет.", "Деревянные жалюзи")
        ]
        cursor.executemany("INSERT INTO products (name, description, category) VALUES (?, ?, ?)", products)
        print("✅ [DB] Тестовые товары добавлены.")

    conn.commit()
    conn.close()

# === Вспомогательные функции ===
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
            f"🔔 *Новая заявка на звонок!*\n\n👤 Имя: {user_name}\n📱 Телефон: `{phone_number}`",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ Ошибка уведомления менеджера: {e}")

# === Yandex ART: получение URL изображения по operation_id ===
def get_image_url_from_operation(operation_id):
    url = f"https://llm.api.cloud.yandex.net/operations/{operation_id}"
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}
    for _ in range(12):  # ждём до 60 сек
        time.sleep(5)
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("done") and "response" in result:
                    return result["response"]["uri"]
        except:
            break
    return None

# === Генерация поста + изображения ===
def generate_post_and_image(product_name, product_description):
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        print("❌ YANDEX_API_KEY или YANDEX_FOLDER_ID не заданы")
        return None, None, None

    # 1. Генерация текста через Yandex GPT
    gpt_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {"Content-Type": "application/json", "Authorization": f"Api-Key {YANDEX_API_KEY}"}
    gpt_prompt = f"""
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

    try:
        gpt_data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
            "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 800},
            "messages": [{"role": "user", "text": gpt_prompt}]
        }
        gpt_resp = requests.post(gpt_url, headers=headers, json=gpt_data, timeout=30)
        gpt_resp.raise_for_status()
        text = gpt_resp.json()['result']['alternatives'][0]['message']['text']

        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            post = json.loads(json_match.group())
            full_content = f"{post['content']}\n\n{' '.join(post['hashtags'])}"
            title = post['title']
        else:
            return None, None, None

    except Exception as e:
        print(f"❌ Ошибка GPT: {e}")
        return None, None, None

    # 2. Генерация изображения через Yandex ART
    art_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
    art_prompt = f"{product_name} в интерьере квартиры в Астрахани. Реалистично, естественный свет, без людей."
    art_data = {
        "modelUri": f"art://{YANDEX_FOLDER_ID}/yandex-art-2.0/latest",
        "messages": [{"text": art_prompt, "weight": "1"}],
        "generationOptions": {"mimeType": "image/jpeg"}
    }

    try:
        art_resp = requests.post(art_url, headers=headers, json=art_data, timeout=30)
        art_resp.raise_for_status()
        op_id = art_resp.json()["id"]
        image_url = get_image_url_from_operation(op_id)
        return title, full_content, image_url
    except Exception as e:
        print(f"❌ Ошибка ART: {e}")
        return title, full_content, None

# === Автопостинг ===
def auto_generate_and_publish_post():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description FROM products ORDER BY RANDOM() LIMIT 1")
    product = cursor.fetchone()
    conn.close()

    if not product:
        print("❌ Нет товаров")
        return

    name, desc = product
    title, content, image_url = generate_post_and_image(name, desc)

    if not title or not content:
        print("❌ Не удалось сгенерировать пост")
        return

    try:
        caption = f"📌 *{title}*\n\n{content}"
        if image_url:
            bot.send_photo(CHANNEL_ID, image_url, caption=caption, parse_mode='Markdown')
            print(f"✅ Пост с изображением опубликован: {title}")
        else:
            bot.send_message(CHANNEL_ID, caption, parse_mode='Markdown')
            print(f"✅ Пост без изображения: {title}")
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")

def send_scheduled_posts():
    print("⏱️ [AUTOPOST] Задача автопостинга запущена")
    last_day = None
    while True:
        now = datetime.now()
        if now.hour == 10 and now.minute == 0:
            today = now.date()
            if last_day != today:
                auto_generate_and_publish_post()
                last_day = today
        time.sleep(60)

def start_autoposting():
    thread = threading.Thread(target=send_scheduled_posts, daemon=True)
    thread.start()
    print("🧵 [AUTOPOST] Автопостинг запущен")

# === Обработчики команд ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Каталог", "🛒 Заказать")
    markup.add("🔗 Канал", "📞 Контакты")
    markup.add("💬 WhatsApp", "ℹ️ Помощь")
    bot.reply_to(message, "👇 Выберите нужный раздел:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def show_contacts(message):
    bot.reply_to(
        message,
        "📍 *Контактная информация*:\n\n"
        "📞 Телефон: +7 (937) 822-29-06\n"
        "💬 WhatsApp: [Написать](https://wa.me/79378222906)\n"
        "✉️ Telegram: [Написать менеджеру](https://t.me/astra_jalyzi30)\n"
        "⏰ Режим работы: 9:00 — 19:00\n"
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

@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    text = "✨ *Выберите категорию:*"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call"))
    markup.add(types.InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/79378222906"))
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=markup)

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
        f"✅ Спасибо, {user_name}!\nМы получили ваш номер: `{phone}`\n📞 Менеджер перезвонит вам в течение 5 минут!",
        parse_mode='Markdown',
        reply_markup=types.ReplyKeyboardRemove()
    )

# === Webhook ===
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        print(f"❌ [WEBHOOK] Ошибка: {e}")
        return 'Error', 500

@app.route('/')
def home():
    global _INITIALIZED
    if not _INITIALIZED:
        init_db()
        add_sample_data()
        set_webhook()
        start_autoposting()
        _INITIALIZED = True
    return jsonify({"status": "running"}), 200

def set_webhook():
    hostname = "alekuk999-telegram-blinds-bot--f681.twc1.net"
    webhook_url = f"https://{hostname}/webhook"
    print(f"🔧 Установка вебхука: {webhook_url}")
    try:
        bot.set_webhook(url=webhook_url)
        print("✅ Вебхук установлен")
    except Exception as e:
        print(f"❌ Ошибка вебхука: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
