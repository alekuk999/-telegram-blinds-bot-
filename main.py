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

# === Настройки Яндекс GPT ===
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
    print("✅ [DB] База данных инициализирована.")

# === Добавление тестовых данных (если пусто) ===
def add_sample_data():
    print("📚 [DB] Проверка и добавление тестовых данных...")
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
                "Рулонные шторы блэкаут",
                "🌙 *Полное затемнение для комфортного сна!*\n\n"
                "• *Функция*: 100% затемнение — идеально для спальни, домашнего кинотеатра.\n"
                "• *Материал*: Трёхслойная ткань с алюминиевым покрытием — отражает тепло и свет.\n"
                "• *Цвета*: Чёрный, тёмно-серый, шоколад, бордо.\n"
                "• *Монтаж*: Внутри или снаружи оконного проёма.",
                0.0,
                "Рулонные шторы",
                "https://img.freepik.com/free-photo/blackout-curtains-bedroom_1268-17832.jpg"
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
        print("✅ [DB] Тестовые товары добавлены.")

    cursor.execute("SELECT COUNT(*) FROM smm_content")
    if cursor.fetchone()[0] == 0:
        print("ℹ️ [DB] Таблица smm_content пуста — посты будут генерироваться через Яндекс GPT.")

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
        print(f"❌ Ошибка сохранения пользователя: {e}")
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
        print(f"❌ Ошибка сохранения сообщения: {e}")
    finally:
        conn.close()

# === Запрос к Яндекс GPT ===
def query_yandex_gpt(user_question):
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        return None  # Возвращаем None, если AI недоступен

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {YANDEX_API_KEY}"
    }

    system_prompt = (
        "Ты — дружелюбный и профессиональный консультант по жалюзи и рулонным шторам в Астрахани. "
        "Отвечай кратко, по делу, на русском языке. Не выдумывай информацию. "
        "Если вопрос не по теме (жалюзи, шторы, материалы, монтаж, цены в Астрахани), вежливо скажи, "
        "что можешь помочь только по теме оконных систем. Предложи написать менеджеру."
    )

    data = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.6,
            "maxTokens": 500
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_question}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        result = response.json()
        answer = result['result']['alternatives'][0]['message']['text']
        return answer.strip()
    except Exception as e:
        print(f"❌ Ошибка GPT: {e}")
        return None

# === Обработчики команд бота ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        save_user(message.from_user)
        save_message(message.from_user.id, message.text, True)
        show_main_menu(message)
    except Exception as e:
        print(f"❌ [BOT] Ошибка в /start: {e}")

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_catalog = types.KeyboardButton("📚 Каталог")
    btn_order = types.KeyboardButton("🛒 Заказать")
    btn_channel = types.KeyboardButton("🔗 Канал")
    btn_contacts = types.KeyboardButton("📞 Контакты")
    btn_whatsapp = types.KeyboardButton("💬 WhatsApp")
    btn_help = types.KeyboardButton("ℹ️ Помощь")
    btn_manager = types.KeyboardButton("👨‍💼 Спросить у менеджера")

    markup.add(btn_catalog, btn_order)
    markup.add(btn_channel, btn_contacts)
    markup.add(btn_whatsapp, btn_help)
    markup.add(btn_manager)

    bot.send_message(message.chat.id, "👇 Выберите нужный раздел:", reply_markup=markup)

# === 🎨 Каталог ===
@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    try:
        save_message(message.from_user.id, message.text, True)
        text = "✨ *Выберите категорию товаров:*"

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_roller = types.InlineKeyboardButton("🧵 Рулонные шторы", callback_data="category_Рулонные шторы")
        btn_horizontal = types.InlineKeyboardButton("🪟 Горизонтальные жалюзи", callback_data="category_Горизонтальные жалюзи")
        btn_vertical = types.InlineKeyboardButton("🚪 Вертикальные жалюзи", callback_data="category_Вертикальные жалюзи")
        btn_whatsapp = types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/79378222906")
        btn_call = types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call")

        markup.add(btn_roller, btn_horizontal, btn_vertical)
        markup.add(btn_whatsapp, btn_call)

        bot.reply_to(message, text, parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        print(f"❌ [CATALOG] Ошибка: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Попробуйте позже.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    try:
        category = call.data.split('_', 1)[1]
        bot.answer_callback_query(call.id, text=f"Вы выбрали: {category}")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, description, image_url 
            FROM products 
            WHERE category = ? AND image_url IS NOT NULL AND image_url != ''
        """, (category,))
        products = cursor.fetchall()
        conn.close()

        if not products:
            bot.send_message(call.message.chat.id, f"📦 В категории *{category}* пока нет товаров.", parse_mode='Markdown')
            return

        bot.send_message(call.message.chat.id, f"📋 *Товары в категории: {category}*", parse_mode='Markdown')

        for product in products:
            name, desc, image_url = product
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call"),
                types.InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/79378222906")
            )

            if image_url.startswith("http"):
                bot.send_photo(
                    chat_id=call.message.chat.id,
                    photo=image_url,
                    caption=f"<b>{name}</b>\n{desc}",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            else:
                bot.send_message(call.message.chat.id, f"❌ Фото недоступно: {name}")

        show_main_menu(call.message)
    except Exception as e:
        print(f"❌ [CATEGORY] Ошибка: {e}")
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# === 📞 Заказать звонок ===
@bot.callback_query_handler(func=lambda call: call.data == "request_call")
def request_call_handler(call):
    try:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "📞 *Пожалуйста, отправьте ваш номер телефона*, и мы перезвоним вам в течение 5 минут!",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardMarkup(
                row_width=1,
                resize_keyboard=True,
                one_time_keyboard=True
            ).add(
                types.KeyboardButton("📲 Отправить мой номер", request_contact=True)
            )
        )
        bot.register_next_step_handler(msg, process_phone_number, call.from_user.first_name)
    except Exception as e:
        print(f"❌ Ошибка в request_call_handler: {e}")

def process_phone_number(message, user_name):
    try:
        phone = message.contact.phone_number if message.contact else message.text.strip()
        if not phone:
            bot.send_message(message.chat.id, "❌ Не удалось получить номер.")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (user_id, user_name, phone, status)
            VALUES (?, ?, ?, ?)
        ''', (message.from_user.id, user_name, phone, "pending"))
        conn.commit()
        conn.close()

        try:
            bot.send_message(
                MANAGER_CHAT_ID,
                f"🔔 *Новая заявка на звонок!*\n\n👤 Имя: {user_name}\n📱 Телефон: `{phone}`",
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"❌ Ошибка уведомления менеджера: {e}")

        bot.send_message(
            message.chat.id,
            f"✅ Спасибо, {user_name}!\n\nМы получили ваш номер: `{phone}`\n📞 Менеджер перезвонит вам в течение 5 минут!",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        print(f"❌ Ошибка в process_phone_number: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# === 👨‍💼 Спросить у менеджера ===
@bot.message_handler(func=lambda m: m.text == "👨‍💼 Спросить у менеджера")
def start_manager_or_ai_chat(message):
    save_message(message.from_user.id, message.text, True)
    bot.send_message(
        message.chat.id,
        "💬 Здравствуйте! Сначала ответит наш AI-помощник.\n\n"
        "Если вопрос сложный или вы хотите поговорить с человеком — напишите:\n"
        "*«Хочу менеджера»*, *«Перезвоните»* или просто опишите задачу.\n\n"
        "Задайте свой вопрос:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, handle_ai_or_forward_to_manager)

def handle_ai_or_forward_to_manager(message):
    user_text = message.text.strip()
    trigger_phrases = ["менеджер", "человек", "связаться", "перезвоните", "позвоните", "оператор", "хочу менеджера", "свяжитесь", "перезвонить", "менеджеру"]
    
    if any(phrase in user_text.lower() for phrase in trigger_phrases):
        forward_to_manager(message)
        return

    # Пытаемся получить ответ от AI
    save_message(message.from_user.id, user_text, True)
    bot.send_chat_action(message.chat.id, 'typing')
    ai_answer = query_yandex_gpt(user_text)

    if ai_answer:
        save_message(message.from_user.id, ai_answer, False)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("🔄 Задать ещё вопрос"))
        markup.add(types.KeyboardButton("👨‍💼 Связаться с менеджером"))
        markup.add(types.KeyboardButton("⬅️ В главное меню"))
        bot.send_message(message.chat.id, ai_answer, reply_markup=markup)
        bot.register_next_step_handler(message, continue_ai_or_manager_flow)
    else:
        # Если AI недоступен — сразу к менеджеру
        bot.send_message(message.chat.id, "🧠 AI-помощник временно недоступен. Ваш запрос передан менеджеру!")
        forward_to_manager(message)

def continue_ai_or_manager_flow(message):
    if message.text == "🔄 Задать ещё вопрос":
        bot.send_message(message.chat.id, "💬 Введите ваш вопрос:")
        bot.register_next_step_handler(message, handle_ai_or_forward_to_manager)
    elif message.text == "👨‍💼 Связаться с менеджером":
        bot.send_message(message.chat.id, "📞 Напишите ваш вопрос или номер телефона:")
        bot.register_next_step_handler(message, forward_to_manager)
    elif message.text == "⬅️ В главное меню":
        show_main_menu(message)
    else:
        handle_ai_or_forward_to_manager(message)

def forward_to_manager(message):
    manager_prompt = (
        "💬 *Вы получили новый запрос от клиента!*\n\n"
        "📌 *Как отвечать:*\n"
        "• Начните с: «Здравствуйте! Спасибо за обращение!»\n"
        "• Уточните: *тип изделия, размеры окна, адрес, удобное время*\n"
        "• Обязательно скажите: *«Замер — бесплатно!»*\n"
        "• Предложите: *скидку 5% при заказе до конца недели*\n"
        "• Попросите номер WhatsApp для связи\n\n"
        "🏢 *Компания:* Рулонные шторы и жалюзи в Астрахани\n"
        "📍 *Адрес:* г. Астрахань, ул. Ленина, д. 10, офис 5\n"
        "📞 *WhatsApp / Telegram:* https://wa.me/79378222906 | https://t.me/astra_jalyzi30\n"
        "🕒 *Режим работы:* ежедневно с 9:00 до 19:00\n\n"
        "🔔 *Данные клиента:*"
    )

    try:
        bot.send_message(
            MANAGER_CHAT_ID,
            f"{manager_prompt}\n"
            f"👤 Имя: {message.from_user.full_name}\n"
            f"🆔 ID: `{message.from_user.id}`\n"
            f"📱 @{message.from_user.username or '—'}\n"
            f"💬 Сообщение: _{message.text}_",
            parse_mode='Markdown'
        )
        bot.send_message(
            message.chat.id,
            "✅ Ваш запрос передан менеджеру! Ожидайте ответа в течение 5 минут.\n\n"
            "А пока вы можете:\n"
            "• Посмотреть 📚 *Каталог*\n"
            "• Написать напрямую в 💬 [WhatsApp](https://wa.me/79378222906)",
            parse_mode='Markdown'
        )
        show_main_menu(message)
    except Exception as e:
        print(f"❌ Ошибка отправки менеджеру: {e}")
        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось передать запрос. Пожалуйста, напишите нам напрямую:\n"
            "[WhatsApp](https://wa.me/79378222906) или [Telegram](https://t.me/astra_jalyzi30)",
            parse_mode='Markdown'
        )
        show_main_menu(message)

# === Остальные разделы ===
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
        "• *WhatsApp* — написать мгновенно\n"
        "• *Спросить у менеджера* — получить помощь\n\n"
        "💡 Все запросы обрабатываются вручную!"
    )

# === 🔥 Вебхук ===
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        print(f"❌ [WEBHOOK] Ошибка: {e}")
        return 'Error', 500

# === Автопостинг ===
def generate_post_with_yandex_gpt(product_name, product_description):
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        print("❌ YANDEX_API_KEY или YANDEX_FOLDER_ID не заданы")
        return None, None

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {YANDEX_API_KEY}"
    }
    prompt = f"""
Ты — маркетолог компании «Рулонные шторы и жалюзи в Астрахани».
Создай цепляющий пост для Telegram-канала на основе описания товара.

Товар: {product_name}
Описание: {product_description}

Пост должен включать:
- Яркий заголовок (не более 50 символов)
- Основной текст (не более 200 символов, с эмодзи)
- 3 хэштега: обязательно #Астрахань, #ЖалюзиАстрахань и один по теме
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
            print("❌ Не удалось извлечь JSON из ответа")
            return None, None
    except Exception as e:
        print(f"❌ Ошибка Yandex GPT: {e}")
        return None, None

def auto_generate_and_publish_post():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, image_url FROM products ORDER BY RANDOM() LIMIT 1")
    product = cursor.fetchone()
    conn.close()

    if not product:
        print("❌ Нет товаров в базе")
        return

    name, desc, image_url = product
    title, content = generate_post_with_yandex_gpt(name, desc)

    if not title or not content:
        print("❌ Не удалось сгенерировать пост")
        return

    try:
        caption = f"📌 *{title}*\n\n{content}"
        if image_url.startswith("http"):
            bot.send_photo(CHANNEL_ID, image_url, caption=caption, parse_mode='Markdown')
        else:
            bot.send_message(CHANNEL_ID, caption, parse_mode='Markdown')
        print(f"✅ Пост опубликован: {title}")
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")

def send_scheduled_posts():
    print("⏱️ [AUTOPOST] Задача автопостинга запущена")
    last_auto_post_day = None
    while True:
        try:
            now = datetime.now()
            if now.hour == 10 and now.minute == 0:
                today = now.date()
                if last_auto_post_day != today:
                    auto_generate_and_publish_post()
                    last_auto_post_day = today
            time.sleep(60)
        except Exception as e:
            print(f"❌ Ошибка в цикле автопостинга: {e}")
            time.sleep(60)

def start_autoposting():
    thread = threading.Thread(target=send_scheduled_posts, daemon=True)
    thread.start()
    print("🧵 [AUTOPOST] Автопостинг запущен как фоновый поток")

# === Главная страница ===
@app.route('/')
def home():
    global _INITIALIZED
    if not _INITIALIZED:
        init_db()
        add_sample_data()
        set_webhook()
        start_autoposting()
        _INITIALIZED = True
    return jsonify({"status": "running", "version": "5.2"}), 200

@app.route('/', methods=['HEAD'])
def head():
    return '', 200

# === Установка вебхука ===
def set_webhook():
    hostname = "alekuk999-telegram-blinds-bot--f681.twc1.net"
    webhook_url = f"https://{hostname}/webhook"
    print(f"🔧 [WEBHOOK] Установка вебхука: {webhook_url}")
    try:
        result = bot.set_webhook(url=webhook_url)
        if result:
            print("✅ [WEBHOOK] Успешно установлен")
        else:
            print("❌ [WEBHOOK] set_webhook вернул False")
    except Exception as e:
        print(f"❌ [WEBHOOK] Ошибка: {e}")

# === Точка входа ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
