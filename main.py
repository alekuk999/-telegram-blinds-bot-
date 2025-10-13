import os
import threading
import time
import logging
from datetime import datetime
import sqlite3
import hashlib

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

CHANNEL_ID = "@astra_jaluzi"
PORT = 8000

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

# === Путь к базе данных ===
DB_PATH = "blinds_bot.db"

# === Ваш Chat ID для уведомлений ===
MANAGER_CHAT_ID = 7126605143  # ← Ваш реальный ID

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

    conn.commit()
    conn.close()
    print("✅ [DB] База данных инициализирована.")

# === Добавление тестовых данных с красивыми описаниями ===
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
                "✨ *Идеально для спальни и гостиной!*"
                "\n\n• 🌞 Чередование прозрачных и плотных полос — регулируйте свет без подъёма шторы."
                "\n• 🧵 Материал: полиэстер с пропиткой — не выгорает, не впитывает запахи."
                "\n• 🎨 Цвета: Белый, бежевый, серый, графит."
                "\n• 📏 Размеры: Под заказ — от 40 см до 300 см в ширину."
                "\n\n✅ Идеально для тех, кто ценит комфорт и стиль!",
                0.0,
                "Рулонные шторы",
                "images/rulonnye_den_noch.jpg"
            ),
            (
                "Рулонные шторы зебра",
                "🎨 *Современный дизайн с эффектом зебры!*"
                "\n\n• 🐆 Два слоя ткани — чередование полос создаёт игру света и тени."
                "\n• ⚙️ Управление: Цепочка или пружинный механизм — плавный ход, без заеданий."
                "\n• 🏠 Применение: Идеальны для кухни, детской, офиса."
                "\n• 🛡️ Гарантия: 3 года на механизм и ткань."
                "\n\n✅ Для тех, кто хочет выделиться!",
                0.0,
                "Рулонные шторы",
                "images/rulonnye_zebra.jpg"
            ),
            (
                "Рулонные шторы блэкаут",
                "🌙 *Полное затемнение для комфортного сна!*"
                "\n\n• 🌑 100% затемнение — идеально для спальни, домашнего кинотеатра."
                "\n• 🛡️ Материал: Трёхслойная ткань с алюминиевым покрытием — отражает тепло и свет."
                "\n• 🎨 Цвета: Чёрный, тёмно-серый, шоколад, бордо."
                "\n• 🏗️ Монтаж: Внутри или снаружи оконного проёма."
                "\n\n✅ Для тех, кто ценит тишину и комфорт!",
                0.0,
                "Рулонные шторы",
                "images/rulonnye_blackout.jpg"
            ),

            # 🪟 Горизонтальные жалюзи
            (
                "Горизонтальные жалюзи алюминиевые",
                "🔧 *Классика, проверенная временем!*"
                "\n\n• 🏭 Материал: Алюминиевые ламели 25 мм — лёгкие, прочные, не ржавеют."
                "\n• 🎨 Цвета: Белый, серебро, золото, дерево, металлик — более 20 оттенков."
                "\n• 🔄 Управление: Поворот ламелей на 180° — регулируйте свет и приватность."
                "\n• 🏡 Применение: Кухня, ванная, балкон — не боятся влаги и пара."
                "\n\n✅ Для тех, кто ценит надёжность и долговечность!",
                0.0,
                "Горизонтальные жалюзи",
                "images/gorizontalnye_aluminievye.jpg"
            ),
            (
                "Горизонтальные жалюзи деревянные",
                "🪵 *Натуральная эстетика и экологичность!*"
                "\n\n• 🌳 Материал: Натуральная древесина — дуб, орех, бук."
                "\n• 🛡️ Прочность: Служат 10+ лет — не деформируются, не выцветают."
                "\n• 🎨 Стиль: Подчеркнут интерьер в стиле «кантри», «эко», «лофт»."
                "\n• 🧽 Уход: Протирайте мягкой сухой тряпкой — не используйте воду."
                "\n\n✅ Для тех, кто ценит натуральность и уют!",
                0.0,
                "Горизонтальные жалюзи",
                "images/gorizontalnye_derevyannye.jpg"
            ),

            # 🚪 Вертикальные жалюзи
            (
                "Вертикальные жалюзи тканевые",
                "🌿 *Элегантность и уют в вашем доме!*"
                "\n\n• 🧵 Ткань: Плотный полиэстер — не выгорает, не впитывает запахи, поглощает шум."
                "\n• 🔄 Управление: Плавный поворот и сдвиг в сторону — легко регулировать освещение."
                "\n• 🎨 Цвета: Пастельные тона — бежевый, серый, молочный, лаванда."
                "\n• 🏢 Применение: Гостиная, спальня, офис — создают ощущение простора."
                "\n\n✅ Для тех, кто ценит уют и стиль!",
                0.0,
                "Вертикальные жалюзи",
                "images/vertikalnye_tkanevye.jpg"
            ),
            (
                "Вертикальные жалюзи ПВХ",
                "💧 *Практично и бюджетно!*"
                "\n\n• 🛡️ Материал: Пластиковые ламели — влагостойкие, не боятся пара и брызг."
                "\n• 🧽 Уход: Легко моются — протрите влажной тряпкой с мыльным раствором."
                "\n• 🎨 Цвета: Белый, бежевый, серый, имитация дерева."
                "\n• 🏡 Применение: Кухня, ванная, балкон — идеальны для влажных помещений."
                "\n\n✅ Для тех, кто ценит практичность и экономию!",
                0.0,
                "Вертикальные жалюзи",
                "images/vertikalnye_pvh.jpg"
            ),

            # 🌀 Жалюзи плиссе
            (
                "Жалюзи плиссе тканевые",
                "🎨 *Изысканный дизайн для нестандартных окон!*"
                "\n\n• 🧵 Форма: Гармошка — идеальны для мансард, эркеров, арочных и треугольных окон."
                "\n• 🧵 Материал: Ткань с эффектом «плиссе» — мягко рассеивает свет, создавая уют."
                "\n• 🔄 Управление: Ручное или автоматическое — можно поднять/опустить любую часть жалюзи."
                "\n• 🎨 Цвета: Пастельные тона — бежевый, серый, молочный — под любой интерьер."
                "\n\n✅ Для тех, кто ценит индивидуальность и изысканность!",
                0.0,
                "Жалюзи плиссе",
                "images/plisse_tkanevye.jpg"
            ),
            (
                "Жалюзи плиссе алюминиевые",
                "🪟 *Современно и функционально!*"
                "\n\n• 🛡️ Материал: Алюминиевые ламели с тканевым покрытием — прочные, долговечные."
                "\n• ☀️ Функция: Отражают солнечные лучи — снижают нагрев помещения летом."
                "\n• 🎨 Цвета: Белый, серебро, золото, бронза."
                "\n• 🏢 Применение: Офисы, переговорные, жилые комнаты с панорамными окнами."
                "\n\n✅ Для тех, кто ценит современность и функциональность!",
                0.0,
                "Жалюзи плиссе",
                "images/plisse_aluminievye.jpg"
            ),

            # 🪵 Деревянные жалюзи
            (
                "Деревянные жалюзи дуб",
                "🌳 *Натуральная роскошь и статус!*"
                "\n\n• 🌳 Материал: Натуральный дуб — прочный, долговечный, экологичный."
                "\n• 🛡️ Прочность: Служат 15+ лет — не деформируются, не выцветают, не боятся солнца."
                "\n• 🎨 Стиль: Подчеркнут интерьер в стиле «кантри», «эко», «премиум»."
                "\n• 🧽 Уход: Протирайте мягкой сухой тряпкой — не используйте воду и химические средства."
                "\n\n✅ Для тех, кто ценит статус и качество!",
                0.0,
                "Деревянные жалюзи",
                "images/derevyannye_dub.jpg"
            ),
            (
                "Деревянные жалюзи орех",
                "🌰 *Тёплый и уютный интерьер!*"
                "\n\n• 🌳 Материал: Натуральный орех — тёплый оттенок, подчёркивает уют."
                "\n• 🛡️ Прочность: Служат 15+ лет — не деформируются, не выцветают, не боятся солнца."
                "\n• 🎨 Стиль: Идеальны для гостиной, спальни, кабинета — создают атмосферу тепла и уюта."
                "\n• 🧽 Уход: Протирайте мягкой сухой тряпкой — не используйте воду и химические средства."
                "\n\n✅ Для тех, кто ценит уют и тепло!",
                0.0,
                "Деревянные жалюзи",
                "images/derevyannye_orekh.jpg"
            )
        ]
        cursor.executemany("INSERT INTO products (name, description, price, category, image_url) VALUES (?, ?, ?, ?, ?)", products)
        print("✅ [DB] Тестовые товары добавлены.")

    conn.commit()
    conn.close()

# === Сохранение данных ===
def save_user(user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)', (user.id, user.username, user.first_name, user.last_name))
        conn.commit()
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователя: {e}")
    finally:
        conn.close()

def save_message(user_id, text, is_from_user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO messages (user_id, message, is_from_user) VALUES (?, ?, ?)', (user_id, text, is_from_user))
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
        
        first_name = message.from_user.first_name or "Клиент"
        welcome_text = (
            f"👋 Привет, {first_name}!\n\n"
            "Я — ваш личный помощник по выбору рулонных штор и жалюзи в Астрахани.\n\n"
            "Что я умею:\n"
            "• 📚 Показать каталог товаров с фото и описаниями\n"
            "• 🧵 Выбрать ткань из 8 категорий (зебра, плиссе, вертикальные и др.)\n"
            "• 📞 Заказать бесплатный замер или звонок менеджера\n"
            "• 🔗 Перейти в наш Telegram-канал\n"
            "• 💬 Написать нам в WhatsApp или Telegram\n\n"
            "👇 Выберите нужный раздел:"
        )
        
        show_main_menu(message, welcome_text)
        
    except Exception as e:
        print(f"❌ [BOT] Ошибка в /start: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Попробуйте позже.")

def show_main_menu(message, custom_text=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Каталог", "🧵 Ткани")
    markup.add("🔗 Канал", "📞 Контакты")
    markup.add("💬 WhatsApp", "ℹ️ Помощь")
    
    if custom_text:
        bot.send_message(message.chat.id, custom_text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "👇 Выберите нужный раздел:", reply_markup=markup)

# === Каталог ===
@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    save_message(message.from_user.id, message.text, True)
    text = "✨ *Выберите категорию товаров:*"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🧵 Рулонные шторы", callback_data="category_Рулонные шторы"))
    markup.add(types.InlineKeyboardButton("🪟 Горизонтальные жалюзи", callback_data="category_Горизонтальные жалюзи"))
    markup.add(types.InlineKeyboardButton("🚪 Вертикальные жалюзи", callback_data="category_Вертикальные жалюзи"))
    markup.add(types.InlineKeyboardButton("🌀 Жалюзи плиссе", callback_data="category_Жалюзи плиссе"))
    markup.add(types.InlineKeyboardButton("🪵 Деревянные жалюзи", callback_data="category_Деревянные жалюзи"))
    markup.add(types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/79378222906"))
    markup.add(types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call"))
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    category = call.data.split('_', 1)[1]
    bot.answer_callback_query(call.id, text=f"Вы выбрали: {category}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, image_url FROM products WHERE category = ?", (category,))
    products = cursor.fetchall()
    conn.close()
    if not products:
        bot.send_message(call.message.chat.id, f"📦 В категории *{category}* пока нет товаров.", parse_mode='Markdown')
        return
    bot.send_message(call.message.chat.id, f"📋 *Товары в категории: {category}*", parse_mode='Markdown')
    for product in products:
        name, desc, image_url = product
        product_key = hashlib.md5(name.encode()).hexdigest()[:8]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔍 Подробнее", callback_data=f"details_{product_key}"),
            types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{product_key}")
        )
        try:
            with open(image_url, 'rb') as photo_file:
                bot.send_photo(call.message.chat.id, photo_file, caption=f"<b>{name}</b>\n{desc}", parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            print(f"❌ Ошибка отправки фото {image_url}: {e}")
            bot.send_message(call.message.chat.id, f"❌ Не удалось загрузить фото для '{name}'.")
    show_main_menu(call.message)

# === 🆕 КНОПКА "ТКАНИ" С ПОДПАПКАМИ ===
@bot.message_handler(func=lambda m: m.text == "🧵 Ткани")
def show_fabric_categories(message):
    categories = [
        "зебра", "рулонка", "плиссе", "вертикальные",
        "вертикальные пластик", "дерево50", "дерево25мм", "алюминий25мм"
    ]
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(cat, callback_data=f"fabric:{cat}") for cat in categories]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🧵 *Выберите категорию ткани:*", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('fabric:'))
def handle_fabric_category(call):
    category = call.data.split(':', 1)[1]
    show_fabric_samples(call.message, category, offset=0)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('fabric_next:'))
def handle_fabric_next(call):
    try:
        _, data = call.data.split(':', 1)
        category, offset_str = data.rsplit(':', 1)
        offset = int(offset_str)
        show_fabric_samples(call.message, category, offset=offset)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"❌ Ошибка обработки 'Показать ещё': {e}")
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "❌ Не удалось загрузить следующую партию. Попробуйте выбрать категорию заново.")

def show_fabric_samples(message, category, offset=0, batch_size=10):
    folder_map = {
        "зебра": "zebra",
        "рулонка": "rulonka",
        "плиссе": "plisse",
        "вертикальные": "vertikalnye",
        "вертикальные пластик": "vertikalnye_plastik",
        "дерево50": "derevo50",
        "дерево25мм": "derevo25mm",
        "алюминий25мм": "alyuminij25mm"
    }
    
    folder = folder_map.get(category)
    if not folder:
        bot.send_message(message.chat.id, "❌ Категория не найдена.")
        return

    path = f"fabric-samples/{folder}"
    if not os.path.exists(path):
        bot.send_message(message.chat.id, f"❌ Папка '{category}' не найдена.")
        return

    all_files = sorted([f for f in os.listdir(path) if f.lower().endswith('.jpg')])
    total = len(all_files)

    if total == 0:
        bot.send_message(message.chat.id, f"В категории '{category}' пока нет образцов.")
        return

    files_to_send = all_files[offset:offset + batch_size]
    for filename in files_to_send:
        try:
            fabric_name = os.path.splitext(filename)[0].replace("_", " ").title()
            with open(f"{path}/{filename}", 'rb') as photo:
                bot.send_photo(
                    message.chat.id, 
                    photo, 
                    caption=f"• *{category}*\n• Артикул: `{fabric_name}`", 
                    parse_mode='Markdown'
                )
        except Exception as e:
            print(f"❌ Ошибка отправки {filename}: {e}")

    if offset + batch_size < total:
        next_offset = offset + batch_size
        callback_data = f"fabric_next:{category}:{next_offset}"
        if len(callback_data.encode('utf-8')) > 64:
            callback_data = callback_data[:60] + "..."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➡️ Показать ещё", callback_data=callback_data))
        bot.send_message(message.chat.id, f"Показано {min(offset+batch_size, total)} из {total} образцов.", reply_markup=markup)

# === Обработчик "Подробнее" ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('details_'))
def handle_details_button(call):
    try:
        product_key = call.data.split('_', 1)[1]
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products")
        all_products = cursor.fetchall()
        conn.close()

        product_name = "товар"
        for (name,) in all_products:
            if hashlib.md5(name.encode()).hexdigest()[:8] == product_key:
                product_name = name
                break

        bot.send_message(
            call.message.chat.id,
            f"📘 *{product_name}*\n\n"
            "Хотите узнать точную цену, выбрать цвет или заказать бесплатный замер?\n\n"
            "📲 Напишите нам удобным способом:",
            parse_mode='Markdown',
            reply_markup=types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/79378222906")],
                [types.InlineKeyboardButton("✉️ Написать в Telegram", url="https://t.me/astra_jalyzi30")]
            ])
        )
        bot.answer_callback_query(call.id)

    except Exception as e:
        print(f"❌ Ошибка в handle_details_button: {e}")
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# === Прочие обработчики ===
@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def show_contacts(message):
    bot.reply_to(message, "📍 *Контактная информация:*\n\n📞 Телефон: +7 (937) 822-29-06\n💬 WhatsApp: [Написать](https://wa.me/79378222906)\n✉️ Telegram: [Написать менеджеру](https://t.me/astra_jalyzi30)\n⏰ Режим работы: 9:00 — 19:00\n🏠 Адрес: г. Астрахань, ул. Ленина, д. 10, офис 5", parse_mode='Markdown', disable_web_page_preview=False)

@bot.message_handler(func=lambda m: m.text == "💬 WhatsApp")
def open_whatsapp(message):
    bot.reply_to(message, "💬 Напишите нам прямо сейчас в WhatsApp:\n\nhttps://wa.me/79378222906", reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("📲 Открыть чат", url="https://wa.me/79378222906")]]))

@bot.message_handler(func=lambda m: m.text == "🔗 Канал")
def open_channel(message):
    bot.reply_to(message, f"📢 Перейдите в наш Telegram-канал:\n\n{CHANNEL_ID}", disable_web_page_preview=False)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def send_help(message):
    bot.reply_to(message, "📌 *Доступные функции бота:*\n\n• *Каталог* — посмотреть все товары с фото\n• *Ткани* — выбрать материал\n• *Контакты* — узнать адрес и телефон\n• *Канал* — новости и акции\n• *WhatsApp* — написать мгновенно\n\n💡 Все запросы обрабатываются вручную — мы перезваниваем в течение 15 минут!", parse_mode='Markdown')

# === 📞 ЗАКАЗ ЗВОНКА (ИСПРАВЛЕНО) ===
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
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

def process_phone_number(message, user_name):
    try:
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = message.text.strip()

        if not phone:
            bot.send_message(message.chat.id, "❌ Не удалось получить номер. Попробуйте снова.")
            return

        save_call_request(message.from_user.id, user_name, phone)
        notify_manager(user_name, phone)

        bot.send_message(
            message.chat.id,
            f"✅ Спасибо, {user_name}!\n\nМы получили ваш номер: `{phone}`\n📞 Менеджер перезвонит вам в течение 5 минут!",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )

        # ✅ ВАЖНО: возвращаем пользователя в главное меню после обработки
        show_main_menu(message)

    except Exception as e:
        print(f"❌ Ошибка в process_phone_number: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        # На всякий случай — тоже возвращаем в меню
        show_main_menu(message)

def save_call_request(user_id, first_name, phone_number):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO orders (user_id, user_name, phone, status)
            VALUES (?, ?, ?, ?)
        ''', (user_id, first_name, phone_number, "pending"))
        conn.commit()
        print(f"📞 [CALL REQUEST] Заявка от {first_name} (ID: {user_id}, Телефон: {phone_number}) сохранена.")
    except Exception as e:
        print(f"❌ Ошибка сохранения заявки: {e}")
    finally:
        conn.close()

def notify_manager(user_name, phone_number):
    try:
        bot.send_message(
            MANAGER_CHAT_ID,
            f"🔔 *Новая заявка на звонок!*\n\n"
            f"👤 Имя: {user_name}\n"
            f"📱 Телефон: `{phone_number}`\n"
            f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown'
        )
        print(f"✅ [NOTIFY] Уведомление отправлено в личный чат (ID: {MANAGER_CHAT_ID})")
    except Exception as e:
        print(f"❌ [NOTIFY] Ошибка отправки уведомления: {e}")
        try:
            bot.send_message(
                MANAGER_CHAT_ID,
                f"⚠️ Не удалось отправить уведомление. Проверьте, что вы написали боту первым.\nОшибка: {e}"
            )
        except:
            pass

# === Вебхук и запуск ===
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def home():
    global _INITIALIZED
    if not _INITIALIZED:
        init_db()
        add_sample_data()
        hostname = "alekuk999-telegram-blinds-bot--f681.twc1.net"
        webhook_url = f"https://{hostname}/webhook"
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
            print(f"✅ [WEBHOOK] Установлен: {webhook_url}")
        except Exception as e:
            print(f"❌ [WEBHOOK] Ошибка: {e}")
        _INITIALIZED = True
    return jsonify({"status": "running", "version": "final"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
