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

CHANNEL_ID = os.getenv("CHANNEL_ID", "@astra_jaluzi")  # Ваш реальный канал
PORT = int(os.getenv("PORT", 8000))  # Исправлено на 8000

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
            # 🧵 Рулонные шторы
            (
                "Рулонные шторы день-ночь",
                "✨ *Идеально для спальни и гостиной!*\n\n"
                "• *Функция*: Чередование прозрачных и плотных полос — регулируйте свет без подъёма шторы.\n"
                "• *Материал*: Полиэстер с пропиткой — не выгорает, не впитывает запахи.\n"
                "• *Цвета*: Белый, бежевый, серый, графит.\n"
                "• *Размеры*: Под заказ — от 40 см до 300 см в ширину.",
                0.0,
                "Рулонные шторы",
                "images/rulonnye_den_noch.jpg"
            ),
            (
                "Рулонные шторы зебра",
                "🎨 *Современный дизайн с эффектом зебры!*\n\n"
                "• *Функция*: Два слоя ткани — чередование полос создаёт игру света и тени.\n"
                "• *Управление*: Цепочка или пружинный механизм — плавный ход, без заеданий.\n"
                "• *Применение*: Идеальны для кухни, детской, офиса.\n"
                "• *Гарантия*: 3 года на механизм и ткань.",
                0.0,
                "Рулонные шторы",
                "images/rulonnye_zebra.jpg"
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
                "images/rulonnye_blackout.jpg"
            ),

            # 🪟 Горизонтальные жалюзи
            (
                "Горизонтальные жалюзи алюминиевые",
                "🔧 *Классика, проверенная временем!*\n\n"
                "• *Материал*: Алюминиевые ламели 25 мм — лёгкие, прочные, не ржавеют.\n"
                "• *Цвета*: Белый, серебро, золото, дерево, металлик — более 20 оттенков.\n"
                "• *Управление*: Поворот ламелей на 180° — регулируйте свет и приватность.\n"
                "• *Применение*: Кухня, ванная, балкон — не боятся влаги и пара.",
                0.0,
                "Горизонтальные жалюзи",
                "images/gorizontalnye_aluminievye.jpg"
            ),
            (
                "Горизонтальные жалюзи деревянные",
                "🪵 *Натуральная эстетика и экологичность!*\n\n"
                "• *Материал*: Натуральная древесина — дуб, орех, бук.\n"
                "• *Прочность*: Служат 10+ лет — не деформируются, не выцветают.\n"
                "• *Стиль*: Подчеркнут интерьер в стиле «кантри», «эко», «лофт».\n"
                "• *Уход*: Протирайте мягкой сухой тряпкой — не используйте воду.",
                0.0,
                "Горизонтальные жалюзи",
                "images/gorizontalnye_derevyannye.jpg"
            ),

            # 🚪 Вертикальные жалюзи
            (
                "Вертикальные жалюзи тканевые",
                "🌿 *Элегантность и уют в вашем доме!*\n\n"
                "• *Ткань*: Плотный полиэстер — не выгорает, не впитывает запахи, поглощает шум.\n"
                "• *Управление*: Плавный поворот и сдвиг в сторону — легко регулировать освещение.\n"
                "• *Цвета*: Пастельные тона — бежевый, серый, молочный, лаванда.\n"
                "• *Применение*: Гостиная, спальня, офис — создают ощущение простора.",
                0.0,
                "Вертикальные жалюзи",
                "images/vertikalnye_tkanevye.jpg"
            ),
            (
                "Вертикальные жалюзи ПВХ",
                "💧 *Практично и бюджетно!*\n\n"
                "• *Материал*: Пластиковые ламели — влагостойкие, не боятся пара и брызг.\n"
                "• *Уход*: Легко моются — протрите влажной тряпкой с мыльным раствором.\n"
                "• *Цвета*: Белый, бежевый, серый, имитация дерева.\n"
                "• *Применение*: Кухня, ванная, балкон — идеальны для влажных помещений.",
                0.0,
                "Вертикальные жалюзи",
                "images/vertikalnye_pvh.jpg"
            ),

            # 🌀 Жалюзи плиссе
            (
                "Жалюзи плиссе тканевые",
                "🎨 *Изысканный дизайн для нестандартных окон!*\n\n"
                "• *Форма*: Гармошка — идеальны для мансард, эркеров, арочных и треугольных окон.\n"
                "• *Материал*: Ткань с эффектом «плиссе» — мягко рассеивает свет, создавая уют.\n"
                "• *Управление*: Ручное или автоматическое — можно поднять/опустить любую часть жалюзи.\n"
                "• *Цвета*: Пастельные тона — бежевый, серый, молочный — под любой интерьер.",
                0.0,
                "Жалюзи плиссе",
                "images/plisse_tkanevye.jpg"
            ),
            (
                "Жалюзи плиссе алюминиевые",
                "🪟 *Современно и функционально!*\n\n"
                "• *Материал*: Алюминиевые ламели с тканевым покрытием — прочные, долговечные.\n"
                "• *Функция*: Отражают солнечные лучи — снижают нагрев помещения летом.\n"
                "• *Цвета*: Белый, серебро, золото, бронза.\n"
                "• *Применение*: Офисы, переговорные, жилые комнаты с панорамными окнами.",
                0.0,
                "Жалюзи плиссе",
                "images/plisse_aluminievye.jpg"
            ),

            # 🪵 Деревянные жалюзи
            (
                "Деревянные жалюзи дуб",
                "🌳 *Натуральная роскошь и статус!*\n\n"
                "• *Материал*: Натуральный дуб — прочный, долговечный, экологичный.\n"
                "• *Прочность*: Служат 15+ лет — не деформируются, не выцветают, не боятся солнца.\n"
                "• *Стиль*: Подчеркнут интерьер в стиле «кантри», «эко», «премиум».\n"
                "• *Уход*: Протирайте мягкой сухой тряпкой — не используйте воду и химические средства.",
                0.0,
                "Деревянные жалюзи",
                "images/derevyannye_dub.jpg"
            ),
            (
                "Деревянные жалюзи орех",
                "🌰 *Тёплый и уютный интерьер!*\n\n"
                "• *Материал*: Натуральный орех — тёплый оттенок, подчёркивает уют.\n"
                "• *Прочность*: Служат 15+ лет — не деформируются, не выцветают, не боятся солнца.\n"
                "• *Стиль*: Идеальны для гостиной, спальни, кабинета — создают атмосферу тепла и уюта.\n"
                "• *Уход*: Протирайте мягкой сухой тряпкой — не используйте воду и химические средства.",
                0.0,
                "Деревянные жалюзи",
                "images/derevyannye_orekh.jpg"
            )
        ]
        cursor.executemany("INSERT INTO products (name, description, price, category, image_url) VALUES (?, ?, ?, ?, ?)", products)
        print("✅ [DB] Тестовые товары добавлены.")

    # SMM контент (можно оставить пустым, т.к. посты генерируются через GPT)
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
        print(f"❌ Ошибка сохранения подписчика: {e}")
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

    markup.add(btn_catalog, btn_order)
    markup.add(btn_channel, btn_contacts)
    markup.add(btn_whatsapp, btn_help)

    bot.send_message(message.chat.id, "👇 Выберите нужный раздел:", reply_markup=markup)

# === 🎨 Каталог с кнопками ===
@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    try:
        save_message(message.from_user.id, message.text, True)
        text = "✨ *Выберите категорию товаров:*"

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_roller = types.InlineKeyboardButton("🧵 Рулонные шторы", callback_data="category_Рулонные шторы")
        btn_horizontal = types.InlineKeyboardButton("🪟 Горизонтальные жалюзи", callback_data="category_Горизонтальные жалюзи")
        btn_vertical = types.InlineKeyboardButton("🚪 Вертикальные жалюзи", callback_data="category_Вертикальные жалюзи")
        btn_pleated = types.InlineKeyboardButton("🌀 Жалюзи плиссе", callback_data="category_Жалюзи плиссе")
        btn_wooden = types.InlineKeyboardButton("🪵 Деревянные жалюзи", callback_data="category_Деревянные жалюзи")
        btn_whatsapp = types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/79378222906")
        btn_call = types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call")

        markup.add(btn_roller, btn_horizontal, btn_vertical, btn_pleated, btn_wooden)
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

            # Генерируем уникальный ключ для кнопок
            product_key = hashlib.md5(name.encode()).hexdigest()[:8]

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔍 Подробнее", callback_data=f"details_{product_key}"),
                types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{product_key}")
            )

            # Отправляем фото
            try:
                if image_url.startswith("http"):
                    bot.send_photo(
                        chat_id=call.message.chat.id,
                        photo=image_url,
                        caption=f"<b>{name}</b>\n{desc}",
                        parse_mode='HTML',
                        reply_markup=markup
                    )
                else:
                    with open(image_url, 'rb') as photo_file:
                        bot.send_photo(
                            chat_id=call.message.chat.id,
                            photo=photo_file,
                            caption=f"<b>{name}</b>\n{desc}",
                            parse_mode='HTML',
                            reply_markup=markup
                        )
            except Exception as e:
                print(f"❌ Ошибка отправки фото {image_url}: {e}")
                bot.send_message(call.message.chat.id, f"❌ Не удалось загрузить фото для '{name}'.")

        show_main_menu(call.message)

    except Exception as e:
        print(f"❌ [CATEGORY] Ошибка: {e}")
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# === 🆕 Обработчик кнопки "Подробнее" ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('details_'))
def handle_details_button(call):
    try:
        product_key = call.data.split('_', 1)[1]
        bot.answer_callback_query(call.id)

        # Ищем товар по описанию
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, description FROM products")
        all_products = cursor.fetchall()
        conn.close()

        # Находим товар, чей хэш совпадает с product_key
        found_product = None
        for name, desc in all_products:
            if hashlib.md5(name.encode()).hexdigest()[:8] == product_key:
                found_product = (name, desc)
                break

        if found_product:
            name, desc = found_product
            extended_info = (
                f"📘 *{name}*\n\n"
                f"{desc}\n\n"
                "✨ *Дополнительная информация:*\n"
                "• *Гарантия*: 3 года на механизм и ткань.\n"
                "• *Срок изготовления*: 3-5 рабочих дней.\n"
                "• *Монтаж*: Бесплатно по Астрахани!\n\n"
                "📞 *Хотите узнать точную цену или заказать замер?*\n"
                "Выберите удобный способ связи:"
            )

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call"))
            markup.add(types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/79378222906"))

            bot.send_message(call.message.chat.id, extended_info, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "❌ Информация не найдена. Попробуйте позже.")

    except Exception as e:
        print(f"❌ Ошибка в handle_details_button: {e}")
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# === Обработчик кнопки "Заказать" (временный) ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('order_'))
def handle_order_button(call):
    try:
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🛒 Чтобы оформить заказ, отправьте мне:\n\n"
            "1. ✏️ Размеры окна (ширина × высота в см)\n"
            "2. 🎨 Цвет или текстура\n"
            "3. 📍 Адрес доставки\n\n"
            "Я перезвоню вам в течение 15 минут!",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ Ошибка в handle_order_button: {e}")
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# === Остальные обработчики ===
@bot.message_handler(func=lambda m: m.text == "🛒 Заказать")
def ask_for_order(message):
    bot.reply_to(
        message,
        "📝 Чтобы оформить заказ, отправьте мне:\n\n"
        "1. ✏️ Размеры окна (ширина × высота в см)\n"
        "2. 🎨 Цвет или текстура\n"
        "3. 📍 Адрес доставки\n\n"
        "Я перезвоню вам в течение 15 минут!"
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
        parse_mode='Markdown',
        disable_web_page_preview=False
    )

@bot.message_handler(func=lambda m: m.text == "💬 WhatsApp")
def open_whatsapp(message):
    whatsapp_url = "https://wa.me/79378222906"
    bot.reply_to(
        message,
        f"💬 Напишите нам прямо сейчас в WhatsApp:\n\n{whatsapp_url}",
        reply_markup=types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("📲 Открыть чат", url=whatsapp_url)]
        ])
    )

@bot.message_handler(func=lambda m: m.text == "🔗 Канал")
def open_channel(message):
    bot.reply_to(
        message,
        f"📢 Перейдите в наш Telegram-канал для акций и новинок:\n\n{CHANNEL_ID}",
        disable_web_page_preview=False
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def send_help(message):
    help_text = (
        "📌 *Доступные функции бота*:\n\n"
        "• *Каталог* — посмотреть все товары с фото и описаниями\n"
        "• *Заказать* — оставить заявку на замер и доставку\n"
        "• *Контакты* — узнать адрес и телефон\n"
        "• *Канал* — подписаться на новости и акции\n"
        "• *WhatsApp* — написать нам мгновенно\n\n"
        "💡 Все запросы обрабатываются вручную — мы перезваниваем в течение 15 минут!"
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')

# === 📞 Обработчик для кнопки "Заказать звонок" ===
@bot.callback_query_handler(func=lambda call: call.data == "request_call")
def request_call_handler(call):
    try:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "📞 *Пожалуйста, отправьте ваш номер телефона*, и мы перезвоним вам в течение 5 минут!\n\n"
            "📱 Вы можете:\n"
            "• Нажать кнопку *«Отправить номер»* ниже\n"
            "• Или ввести номер вручную (например: `+79271234567`)",
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

        save_call_request(message.from_user.id, user_name, phone)
        notify_manager(user_name, phone)

        bot.send_message(
            message.chat.id,
            f"✅ Спасибо, {user_name}!\n\nМы получили ваш номер: `{phone}`\n📞 Менеджер перезвонит вам в течение 5 минут!",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        print(f"❌ Ошибка в process_phone_number: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

def save_call_request(user_id, first_name, phone_number):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO orders (user_id, user_name, phone, status)
            VALUES (?, ?, ?, ?)
        ''', (user_id, first_name, phone_number, "pending"))
        conn.commit()
    except Exception as e:
        print(f"❌ Ошибка сохранения заявки: {e}")
    finally:
        conn.close()

def notify_manager(user_name, phone_number):
    try:
        bot.send_message(
            MANAGER_CHAT_ID,
            f"🔔 *Новая заявка на звонок!*\n\n👤 Имя: {user_name}\n📱 Телефон: `{phone_number}`\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

# === 🔥 Вебхук для Telegram ===
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

# === 🆕 Функция генерации поста с помощью Яндекс GPT ===
def generate_post_with_yandex_gpt(product_name, product_description):
    """Генерирует пост для Telegram-канала с помощью Яндекс GPT."""
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        print("❌ Яндекс API ключ или Folder ID не установлен.")
        return None, None

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {YANDEX_API_KEY}"
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
    - Призыв к действию (написать в WhatsApp или заказать звонок)

    Ответь в формате JSON:
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
            "maxTokens": "1000"
        },
        "messages": [
            {
                "role": "user",
                "text": prompt
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        result = response.json()
        text = result['result']['alternatives'][0]['message']['text']

        # Парсим JSON из ответа
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            post_data = json.loads(json_match.group())
            full_content = f"{post_data['content']}\n\n{' '.join(post_data['hashtags'])}"
            return post_data['title'], full_content
        else:
            return None, None
    except Exception as e:
        print(f"❌ Ошибка Яндекс GPT: {e}")
        return None, None

# === 🆕 Функция для автоматической публикации поста ===
def auto_generate_and_publish_post():
    """Автоматически генерирует и публикует пост в канал."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Выбираем случайный товар
    cursor.execute("SELECT name, description, image_url FROM products ORDER BY RANDOM() LIMIT 1")
    product = cursor.fetchone()

    if not product:
        print("❌ Нет товаров в базе данных.")
        return

    name, desc, image_url = product

    # Генерируем пост с помощью Яндекс GPT
    title, content = generate_post_with_yandex_gpt(name, desc)

    if not title or not content:
        print("❌ Не удалось сгенерировать пост.")
        return

    # Публикуем пост в канал
    try:
        if image_url.startswith("http"):
            bot.send_photo(CHANNEL_ID, image_url, caption=f"📌 *{title}*\n\n{content}", parse_mode='Markdown')
        else:
            with open(image_url, 'rb') as photo_file:
                bot.send_photo(CHANNEL_ID, photo_file, caption=f"📌 *{title}*\n\n{content}", parse_mode='Markdown')
        print(f"✅ Пост опубликован: {title}")
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")

    conn.close()

# === Автопостинг в канал по дням недели + AI ===
def send_scheduled_posts():
    print("⏱️ [AUTOPOST] Задача автопостинга запущена")
    last_auto_post = 0
    while True:
        try:
            now = datetime.now()
            current_weekday = now.weekday()
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')

            # Публикуем автоматический пост раз в день (в 10:00)
            if now.hour == 10 and now.minute == 0 and last_auto_post != now.day:
                auto_generate_and_publish_post()
                last_auto_post = now.day

            # Проверяем запланированные посты (из базы smm_content)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, title, content, image_url, category 
                FROM smm_content 
                WHERE is_published = 0 
                AND scheduled_time <= ?
                AND (weekday IS NULL OR weekday = ?)
                ORDER BY scheduled_time
                LIMIT 1
            """, (now_str, current_weekday))

            row = cursor.fetchone()
            if row:
                content_id, title, content, image_url, category = row
                message = f"📌 <b>{title}</b>\n\n{content}\n\n#{category.replace(' ', '_')}"

                try:
                    if image_url.startswith("http"):
                        bot.send_photo(CHANNEL_ID, image_url.strip(), caption=message, parse_mode='HTML')
                    else:
                        with open(image_url, 'rb') as photo_file:
                            bot.send_photo(CHANNEL_ID, photo_file, caption=message, parse_mode='HTML')
                    cursor.execute("UPDATE smm_content SET is_published = 1 WHERE id = ?", (content_id,))
                    conn.commit()
                    print(f"✅ [AUTOPOST] Пост опубликован: {title}")
                except Exception as e:
                    print(f"❌ [AUTOPOST] Ошибка отправки в канал {CHANNEL_ID}: {e}")
            conn.close()

        except Exception as e:
            print(f"❌ [AUTOPOST] Ошибка: {e}")
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
    return jsonify({"status": "running", "version": "5.0"}), 200

@app.route('/', methods=['HEAD'])
def head():
    return '', 200

def set_webhook():
    hostname = os.getenv('HOSTNAME', 'your-app.twc1.net').strip()
    webhook_url = f"https://{hostname}/webhook"
    try:
        result = bot.set_webhook(url=webhook_url)
        if result:
            print(f"✅ [WEBHOOK] Установлен: {webhook_url}")
        else:
            print(f"❌ [WEBHOOK] Не удалось установить.")
    except Exception as e:
        print(f"❌ [WEBHOOK] Ошибка: {e}")

# === Точка входа ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
