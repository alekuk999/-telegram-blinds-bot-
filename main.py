import os
import threading
import time
import logging
from datetime import datetime

# === Отключаем лишние логи ===
logging.getLogger("gunicorn").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

import sqlite3
from flask import Flask, request, jsonify
import telebot
from telebot import types

# === Настройки приложения ===
app = Flask(__name__)

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не установлена!")

CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")  # Замените на свой или задайте в Render
PORT = int(os.getenv("PORT", 10000))

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

# === Путь к базе данных ===
DB_PATH = "blinds_bot.db"

# === Инициализация базы данных ===
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

# === Добавление тестовых данных ===
def add_sample_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Товары
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ("Рулонные шторы день-ночь", "Современные рулонные шторы с двумя режимами затемнения", 2490.0, "Рулонные шторы", "https://placehold.co/300x200/4b6cb7/white?text=День-Ночь"),
            ("Вертикальные жалюзи", "Стильные вертикальные жалюзи для больших окон", 3290.0, "Жалюзи", "https://placehold.co/300x200/182848/white?text=Вертикальные"),
            ("Горизонтальные алюминиевые жалюзи", "Классические жалюзи с регулировкой угла наклона", 1890.0, "Жалюзи", "https://placehold.co/300x200/3a5ca5/white?text=Алюминий"),
            ("Римские шторы", "Элегантные римские шторы с ручным управлением", 3990.0, "Шторы", "https://placehold.co/300x200/ff6b6b/white?text=Римские"),
            ("Рулонные шторы зебра", "Современные шторы зебра с чередующимися полосами", 2790.0, "Рулонные шторы", "https://placehold.co/300x200/27ae60/white?text=Зебра"),
            ("Деревянные жалюзи", "Натуральные деревянные жалюзи премиум класса", 4590.0, "Жалюзи", "https://placehold.co/300x200/f39c12/white?text=Дерево")
        ]
        cursor.executemany("INSERT INTO products (name, description, price, category, image_url) VALUES (?, ?, ?, ?, ?)", products)

    # SMM контент
    cursor.execute("SELECT COUNT(*) FROM smm_content")
    if cursor.fetchone()[0] == 0:
        smm_content = [
            ("5 причин выбрать рулонные шторы", "Рулонные шторы - идеальное решение для современного интерьера. Они практичны, красивы и функциональны!", "https://placehold.co/600x400/4b6cb7/white?text=Рулонные+шторы", "Образование", None, 1),
            ("Как выбрать жалюзи для кухни", "Кухня требует особого подхода к выбору жалюзи. Рассказываем, на что обратить внимание!", "https://placehold.co/600x400/182848/white?text=Жалюзи+для+кухни", "Советы", None, 1),
            ("Тренды 2023: Что в моде у штор", "Следите за модой и в интерьере! Рассказываем о главных трендах в мире штор этого года.", "https://placehold.co/600x400/ff6b6b/white?text=Тренды+2023", "Тренды", None, 1),
            ("Сравнение материалов: Ткань vs ПВХ", "Какой материал выбрать для рулонных штор? Разбираемся в плюсах и минусах каждого варианта.", "https://placehold.co/600x400/27ae60/white?text=Материалы", "Образование", None, 1),
            ("Дизайн спальни с идеальными шторами", "Создайте уютную атмосферу в спальне с помощью правильно подобранных штор!", "https://placehold.co/600x400/f39c12/white?text=Дизайн+спальни", "Дизайн", None, 1)
        ]
        cursor.executemany("INSERT INTO smm_content (title, content, image_url, category, scheduled_time, is_published) VALUES (?, ?, ?, ?, ?, ?)", smm_content)

    conn.commit()
    conn.close()

# === Сохранение данных ===
def save_user(user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user.id, user.username, user.first_name, user.last_name))
        conn.commit()
    except Exception as e:
        print(f"Ошибка сохранения пользователя: {e}")
    finally:
        conn.close()

def save_subscriber(user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO subscribers (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user.id, user.username, user.first_name, user.last_name))
        conn.commit()
    except Exception as e:
        print(f"Ошибка сохранения подписчика: {e}")
    finally:
        conn.close()

def save_message(user_id, text, is_from_user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO messages (user_id, message, is_from_user)
            VALUES (?, ?, ?)
        ''', (user_id, text, is_from_user))
        conn.commit()
    except Exception as e:
        print(f"Ошибка сохранения сообщения: {e}")
    finally:
        conn.close()

# === Обработчики команд бота ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user(message.from_user)
    save_message(message.from_user.id, message.text, True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍 Каталог", "🎯 Заказать")
    markup.add("📢 Канал", "📞 Контакты")
    markup.add("ℹ️ О нас", "📚 Полезное")
    bot.reply_to(message, "🌟 Добро пожаловать в BlindStyle!\n\nВыберите раздел:", reply_markup=markup)

@bot.message_handler(commands=['help'])
def send_help(message):
    save_message(message.from_user.id, message.text, True)
    help_text = "Доступные команды: /start, /help, и кнопки меню."
    bot.reply_to(message, help_text)

@bot.message_handler(func=lambda m: m.text == "🛍 Каталог")
def show_catalog(message):
    save_message(message.from_user.id, message.text, True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    if products:
        bot.reply_to(message, "📋 Наш каталог товаров:")
        for p in products:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔍 Подробнее", callback_data=f"details_{p[0]}"),
                types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{p[0]}")
            )
            bot.send_photo(message.chat.id, p[5], caption=f"<b>{p[1]}</b>\n{p[2]}\n💰 {p[3]:.2f} руб.", parse_mode='HTML', reply_markup=markup)
    else:
        bot.reply_to(message, "Каталог пуст.")

# === 🔍 ЭХО-ОБРАБОТЧИК ДЛЯ ОТЛАДКИ ===
# Этот обработчик ловит ВСЕ сообщения, которые не были обработаны выше.
@bot.message_handler(func=lambda message: True)
def debug_echo_handler(message):
    user_info = f"ID: {message.from_user.id}, Имя: {message.from_user.first_name}"
    print(f"📩 [DEBUG] Получено сообщение от {user_info}: '{message.text}'")
    # bot.reply_to(message, "🔧 [DEBUG] Бот получил ваше сообщение!") # Раскомментируйте для теста эха

# === Автопостинг в канал ===
def send_scheduled_posts():
    """Фоновая задача: публикует посты в канале по расписанию"""
    while True:
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, title, content, image_url, category 
                FROM smm_content 
                WHERE is_published = 0 
                AND scheduled_time <= ?
                ORDER BY scheduled_time
                LIMIT 1
            """, (now,))

            row = cursor.fetchone()
            if row:
                content_id, title, content, image_url, category = row
                message = f"""
📌 <b>{title}</b>

{content}

#{category.replace(' ', '_')}
                """
                try:
                    if image_url and "placeholder" not in image_url.lower():
                        bot.send_photo(CHANNEL_ID, image_url.strip(), caption=message, parse_mode='HTML')
                    else:
                        bot.send_message(CHANNEL_ID, message, parse_mode='HTML')
                    cursor.execute("UPDATE smm_content SET is_published = 1 WHERE id = ?", (content_id,))
                    conn.commit()
                    print(f"✅ Пост опубликован: {title}")
                except Exception as e:
                    print(f"❌ Ошибка отправки в канал {CHANNEL_ID}: {e}")
            conn.close()
        except Exception as e:
            print(f"❌ Ошибка в автопостинге: {e}")
        time.sleep(60)  # Проверяем каждую минуту

def start_autoposting():
    thread = threading.Thread(target=send_scheduled_posts, daemon=True)
    thread.start()
    print("🧵 Автопостинг запущен")

# === 🔥 ГЛАВНОЕ ИСПРАВЛЕНИЕ: Обработчик для /webhook ===
@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Этот эндпоинт принимает POST-запросы от Telegram API.
    """
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200  # Всегда возвращаем 200 OK

# === Главная страница (для мониторинга и health-check) ===
@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "BlindStyle SMM Bot Service",
        "version": "1.2",
        "message": "Bot is online. Webhook is set to /webhook"
    }), 200

# === HEAD / для Gunicorn ===
@app.route('/', methods=['HEAD'])
def head():
    return '', 200

# === Установка вебхука ===
def set_webhook():
    """
    Устанавливает вебхук для Telegram бота.
    """
    webhook_url = f"https://telegram-blinds-bot-1.onrender.com/webhook"
    print(f"🔧 Попытка установить вебхук на: {webhook_url}")

    try:
        # Удаляем старый вебхук
        result_remove = bot.remove_webhook()
        print(f"🗑 Старый вебхук удален: {result_remove}")

        # Пауза для надежности
        time.sleep(1)

        # Устанавливаем новый вебхук
        result_set = bot.set_webhook(url=webhook_url)
        if result_set:
            print(f"✅ Вебхук успешно установлен: {webhook_url}")
        else:
            print(f"❌ Ошибка: метод set_webhook вернул False для URL: {webhook_url}")

    except Exception as e:
        print(f"❌ Исключение при установке вебхука: {e}")
        import traceback
        traceback.print_exc()

# === Инициализация ===
def initialize():
    print("🔄 Начинаем инициализацию...")
    init_db()
    add_sample_data()
    set_webhook()
    start_autoposting()
    print("✅ Инициализация завершена")

# 🔥🔥🔥 ВАЖНЕЙШАЯ ЧАСТЬ 🔥🔥🔥
# Вызываем initialize() СРАЗУ, при импорте модуля.
# Это необходимо для работы на Render с Gunicorn.
initialize()

# === Запуск (Render использует Gunicorn, этот блок игнорируется) ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
