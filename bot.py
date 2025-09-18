import os
import threading
import time
import logging
from datetime import datetime, time as dt_time
import sqlite3
import hashlib
import openai

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("gunicorn").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from flask import Flask, request, jsonify
import telebot
from telebot import types

# === Конфигурация ===
app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не установлен!")

CHANNEL_ID = os.getenv("CHANNEL_ID", "@astra_jaluzi")
PORT = int(os.getenv("PORT", 8000))

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

# === OpenAI — твой ключ уже вшит ===
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY

# === База данных ===
DB_PATH = "blinds_bot.db"
MANAGER_CHAT_ID = 7126605143
_INITIALIZED = False

# === Инициализация БД ===
def init_db():
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
        CREATE TABLE IF NOT EXISTS smm_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            category TEXT,
            scheduled_time TIMESTAMP,
            is_published BOOLEAN DEFAULT 0,
            weekday INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных готова.")

# === Тестовые данные ===
def add_sample_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ("Рулонные шторы день-ночь", "✨ Идеально для спальни! Чередование прозрачных и плотных полос. Материал: полиэстер. Цвета: белый, бежевый, серый.", 0.0, "Рулонные шторы", "https://i.imgur.com/rulon_day_night.jpg"),
            ("Горизонтальные жалюзи алюминиевые", "🔧 Классика! Ламели 25 мм, не ржавеют. Цвета: белый, серебро, дерево. Для кухни и ванной.", 0.0, "Горизонтальные жалюзи", "https://i.imgur.com/horiz_alum.jpg"),
            ("Вертикальные жалюзи ПВХ", "💧 Практично! Влагостойкие, легко моются. Цвета: белый, бежевый, имитация дерева. Для кухни и балкона.", 0.0, "Вертикальные жалюзи", "https://i.imgur.com/vert_pvh.jpg"),
        ]
        cursor.executemany("INSERT INTO products (name, description, price, category, image_url) VALUES (?, ?, ?, ?, ?)", products)
        print("✅ Тестовые товары добавлены.")
    conn.commit()
    conn.close()

# === Генерация поста через OpenAI ===
def generate_smm_post_with_ai(topic):
    system_prompt = f"""
Ты — маркетолог в Астрахани, продаёшь жалюзи и рулонные шторы.
Создай пост для Telegram-канала {CHANNEL_ID} — “РУЛОННЫЕ ШТОРЫ ЖАЛЮЗИ АСТРАХАНЬ”.

Формат:
- Заголовок (до 8 слов, с эмодзи)
- Текст (до 400 символов, абзацы, 1–3 эмодзи)
- Призыв: “Пишите в ЛС”, “Звоните”, “Успейте до...”
- Хэштеги: #Астрахань #жалюзиАстрахань #рулонныешторыАстрахань

Обязательно упомяни:
- Астраханскую жару — “спасём от +40°C”
- Быструю установку — “за 1 день”
- Бесплатный замер
- WhatsApp: https://wa.me/79378222906
Тон: дружелюбный, местный, экспертный.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Создай пост на тему: {topic}"}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"❌ OpenAI ошибка: {e}")
        return None

# === Сохранение и публикация поста ===
def save_and_publish_post(topic, content):
    if not content:
        return False

    # Сохраняем в БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO smm_content (title, content, category, scheduled_time, is_published)
        VALUES (?, ?, ?, ?, ?)
    ''', (topic, content, "AI-генерация", datetime.now(), 1))
    conn.commit()
    conn.close()

    # Публикуем в канал
    try:
        bot.send_message(CHANNEL_ID, content, parse_mode='HTML')
        logging.info(f"✅ Пост опубликован: {topic}")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка публикации: {e}")
        return False

# === Автопостинг в 9:00 ===
def ai_autoposting_worker():
    logging.info("🤖 AI-автопостинг запущен")
    last_post_date = None

    while True:
        try:
            now = datetime.now()
            if last_post_date == now.date():
                time.sleep(60)
                continue

            if now.time() >= dt_time(9, 0):
                topics = [
                    "Почему рулонные шторы лучше занавесок?",
                    "Как выбрать жалюзи для кухни?",
                    "Скидка 20% на жалюзи этой неделей",
                    "Жалюзи для детской — безопасно и стильно",
                    "Защита от астраханской жары",
                    "Тренды 2025 в мире жалюзи",
                    "Быстрая установка — за 1 день!",
                    "Бесплатный замер в Астрахани",
                ]
                topic = topics[now.day % len(topics)]

                logging.info(f"🧠 Генерирую пост: {topic}")
                post = generate_smm_post_with_ai(topic)

                if post and save_and_publish_post(topic, post):
                    last_post_date = now.date()
                    logging.info(f"🎉 Успешно: {topic}")

            time.sleep(60)
        except Exception as e:
            logging.error(f"❌ Ошибка в автопостинге: {e}")
            time.sleep(60)

def start_ai_autoposting():
    thread = threading.Thread(target=ai_autoposting_worker, daemon=True)
    thread.start()

# === Простой обработчик /start ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, f"Привет! Я бот компании *РУЛОННЫЕ ШТОРЫ ЖАЛЮЗИ АСТРАХАНЬ*.\nКанал: {CHANNEL_ID}\nWhatsApp: https://wa.me/79378222906", parse_mode='Markdown')

# === Вебхук ===
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

# === Инициализация при запуске ===
@app.route('/')
def home():
    global _INITIALIZED
    if not _INITIALIZED:
        init_db()
        add_sample_data()
        start_ai_autoposting()
        _INITIALIZED = True
    return jsonify({"status": "running", "channel": CHANNEL_ID}), 200

# === Запуск ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
