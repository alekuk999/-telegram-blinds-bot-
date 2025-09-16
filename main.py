import os
import threading
import time
import logging
from datetime import datetime
import sqlite3

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

CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")  # ← ЗАМЕНИ НА СВОЙ КАНАЛ!
PORT = int(os.getenv("PORT", 443))  # 🔥 ИСПРАВЛЕНО: 443 вместо 8000

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

# === Путь к базе данных ===
DB_PATH = "blinds_bot.db"

# === Ваш Chat ID для уведомлений ===
MANAGER_CHAT_ID = 7126605143  # 🔥 УВЕДОМЛЕНИЯ ПРИХОДЯТ СЮДА (в ваш личный чат)

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
                0.0,  # ← Цена удалена (но поле оставлено для совместимости)
                "Рулонные шторы",
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
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
                "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"
            )
        ]
        cursor.executemany("INSERT INTO products (name, description, price, category, image_url) VALUES (?, ?, ?, ?, ?)", products)
        print("✅ [DB] Тестовые товары добавлены.")

    # SMM контент (оставляем как есть)
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
        print("✅ [DB] Тестовый SMM контент добавлен.")

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
        print(f"🤖 [BOT] Обработчик /start вызван для пользователя {message.from_user.id}")
        save_user(message.from_user)
        save_message(message.from_user.id, message.text, True)

        show_main_menu(message)

        print(f"✅ [BOT] Приветственное меню отправлено пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике /start: {e}")
        import traceback
        traceback.print_exc()


def show_main_menu(message):
    """Показывает главное меню"""
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

    bot.send_message(
        message.chat.id,
        "👇 Выберите нужный раздел:",
        reply_markup=markup
    )


# === 🎨 КРАСИВО ОФОРМЛЕННЫЙ КАТАЛОГ С КНОПКАМИ ===
@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    try:
        print(f"🤖 [BOT] Обработчик 'Каталог' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        # 🎨 Красивое оформление — БЕЗ ССЫЛКИ НА САЙТ
        text = (
            "✨ *Выберите категорию товаров:*\n\n"
            "👇 Нажмите на нужную категорию, чтобы увидеть ассортимент."
        )

        # 🎛 Inline-кнопки — категории
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_roller = types.InlineKeyboardButton("🧵 Рулонные шторы", callback_data="category_Рулонные шторы")
        btn_horizontal = types.InlineKeyboardButton("🪟 Горизонтальные жалюзи", callback_data="category_Горизонтальные жалюзи")
        btn_vertical = types.InlineKeyboardButton("🚪 Вертикальные жалюзи", callback_data="category_Вертикальные жалюзи")
        btn_pleated = types.InlineKeyboardButton("🌀 Жалюзи плиссе", callback_data="category_Жалюзи плиссе")
        btn_wooden = types.InlineKeyboardButton("🪵 Деревянные жалюзи", callback_data="category_Деревянные жалюзи")
        btn_whatsapp = types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/+79378222906")
        btn_call = types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call")

        markup.add(btn_roller, btn_horizontal, btn_vertical, btn_pleated, btn_wooden)
        markup.add(btn_whatsapp, btn_call)

        bot.reply_to(
            message,
            text,
            parse_mode='Markdown',
            reply_markup=markup,
            disable_web_page_preview=False
        )

        print(f"✅ [CATALOG] Меню категорий отправлено пользователю {message.from_user.id}")

    except Exception as e:
        print(f"❌ [CATALOG] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        bot.reply_to(message, "❌ Произошла ошибка при загрузке каталога. Попробуйте позже.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    try:
        category = call.data.split('_', 1)[1]
        print(f"📦 [CATALOG] Пользователь выбрал категорию: {category}")

        bot.answer_callback_query(call.id, text=f"Вы выбрали: {category}")

        # Получаем товары из выбранной категории
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
                types.InlineKeyboardButton("🔍 Подробнее", callback_data=f"details_{name}"),
                types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{name}")
            )

            bot.send_photo(
                chat_id=call.message.chat.id,
                photo=image_url,
                caption=f"<b>{name}</b>\n{desc}",
                parse_mode='HTML',
                reply_markup=markup
            )

        # ✅ ДОБАВЛЕНО: Кнопка "Назад в меню"
        show_main_menu(call.message)

        print(f"✅ [CATALOG] Отправлено {len(products)} товаров пользователю {call.from_user.id}")

    except Exception as e:
        print(f"❌ [CATEGORY] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(func=lambda m: m.text == "🛒 Заказать")
def ask_for_order(message):
    try:
        print(f"🤖 [BOT] Обработчик 'Заказать' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        bot.reply_to(
            message,
            "📝 Чтобы оформить заказ, отправьте мне:\n\n"
            "1. ✏️ Размеры окна (ширина × высота в см)\n"
            "2. 🎨 Цвет или текстура (например: белый матовый, дуб светлый)\n"
            "3. 📍 Адрес доставки (город, улица, дом, квартира)\n\n"
            "Я перезвоню вам в течение 15 минут и подтвержу стоимость!"
        )
        print(f"✅ [BOT] Инструкция по заказу отправлена пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'Заказать': {e}")
        import traceback
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def show_contacts(message):
    try:
        print(f"🤖 [BOT] Обработчик 'Контакты' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        bot.reply_to(
            message,
            "📍 *Контактная информация*:\n\n"
            "📞 Телефон: +7 (937) 822-29-06\n"
            "💬 WhatsApp: [Написать](https://wa.me/+79378222906)\n"
            "✉️ Telegram: [Написать менеджеру](https://t.me/astra_jalyzi30)\n"  # ✅ ДОБАВЛЕНА ССЫЛКА НА TELEGRAM
            "⏰ Режим работы: 9:00 — 19:00 (ежедневно)\n"
            "🏠 Адрес: г. Астрахань, ул. Ленина, д. 10, офис 5",
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
        print(f"✅ [BOT] Контакты отправлены пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'Контакты': {e}")
        import traceback
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.text == "💬 WhatsApp")
def open_whatsapp(message):
    try:
        print(f"🤖 [BOT] Обработчик 'WhatsApp' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        whatsapp_number = "+79378222906"
        whatsapp_url = f"https://wa.me/{whatsapp_number}"  # ✅ ИСПРАВЛЕНО: УБРАН ЛИШНИЙ ПРОБЕЛ

        bot.reply_to(
            message,
            f"💬 Напишите нам прямо сейчас в WhatsApp:\n\n"
            f"{whatsapp_url}\n\n"
            "Мы ответим в течение 10 минут!",
            disable_web_page_preview=False,
            reply_markup=types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("📲 Открыть чат", url=whatsapp_url)]
            ])
        )
        print(f"✅ [BOT] Ссылка на WhatsApp отправлена пользователю {message.from_user.id}")

    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'WhatsApp': {e}")
        import traceback
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.text == "🔗 Канал")
def open_channel(message):
    try:
        print(f"🤖 [BOT] Обработчик 'Канал' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        bot.reply_to(
            message,
            f"📢 Перейдите в наш Telegram-канал для акций и новинок:\n\n{CHANNEL_ID}\n\n(нажмите на ссылку выше)",
            disable_web_page_preview=False
        )
        print(f"✅ [BOT] Ссылка на канал отправлена пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'Канал': {e}")
        import traceback
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def send_help(message):
    try:
        print(f"🤖 [BOT] Обработчик 'Помощь' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

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
        print(f"✅ [BOT] Сообщение помощи отправлено пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'Помощь': {e}")
        import traceback
        traceback.print_exc()


# === Обработчик inline-кнопок (детали и заказ) ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('details_') or call.data.startswith('order_'))
def handle_inline_button(call):
    try:
        data = call.data
        product_name = data.split('_', 1)[1]

        if data.startswith('details_'):
            bot.answer_callback_query(call.id, text=f"Подробности: {product_name}")
            bot.send_message(
                call.message.chat.id,
                f"📘 *{product_name}*\n\n"
                "Вы можете оформить заказ через кнопку «Заказать» в главном меню.\n"
                "Или напишите нам в WhatsApp — мы поможем подобрать идеальный вариант!",
                parse_mode='Markdown'
            )

        elif data.startswith('order_'):
            bot.answer_callback_query(call.id, text=f"Заказ: {product_name}")
            bot.send_message(
                call.message.chat.id,
                f"🛒 Вы выбрали: *{product_name}*\n\n"
                "Чтобы оформить заказ, отправьте мне:\n"
                "1. Размеры окна (ширина × высота в см)\n"
                "2. Цвет или текстура\n"
                "3. Адрес доставки\n\n"
                "Я перезвоню вам в течение 15 минут!",
                parse_mode='Markdown'
            )

    except Exception as e:
        print(f"❌ [INLINE] Ошибка обработки inline-кнопки: {e}")
        import traceback
        traceback.print_exc()


# === 📞 Обработчик для кнопки "Заказать звонок" ===
@bot.callback_query_handler(func=lambda call: call.data == "request_call")
def request_call_handler(call):
    try:
        user = call.from_user

        # Отправляем сообщение с запросом номера
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

        # Регистрируем следующий шаг — ожидаем номер
        bot.register_next_step_handler(msg, process_phone_number, user.first_name)

    except Exception as e:
        print(f"❌ Ошибка в request_call_handler: {e}")


def process_phone_number(message, user_name):
    try:
        phone = None

        # Если пользователь отправил контакт
        if message.contact:
            phone = message.contact.phone_number
        # Если ввёл вручную
        elif message.text:
            phone = message.text.strip()

        if not phone:
            bot.send_message(message.chat.id, "❌ Не удалось получить номер. Попробуйте снова.")
            return

        # Сохраняем заявку в базу
        save_call_request(message.from_user.id, user_name, phone)

        # ✅ ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ В ВАШ ЛИЧНЫЙ ЧАТ
        notify_manager(user_name, phone)

        # Отправляем подтверждение пользователю
        bot.send_message(
            message.chat.id,
            f"✅ Спасибо, {user_name}!\n\n"
            f"Мы получили ваш номер: `{phone}`\n"
            "📞 Менеджер перезвонит вам в течение 5 минут!",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )

    except Exception as e:
        print(f"❌ Ошибка в process_phone_number: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def save_call_request(user_id, first_name, phone_number):
    """Сохраняет заявку на обратный звонок в базу данных"""
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


# === 📲 Функция для отправки уведомления в ваш личный чат ===
def notify_manager(user_name, phone_number):
    """Отправляет уведомление в ваш личный чат (не в бота!)"""
    try:
        bot.send_message(
            MANAGER_CHAT_ID,  # ← Сообщение приходит СЮДА — в ваш личный чат
            f"🔔 *Новая заявка на звонок!*\n\n"
            f"👤 Имя: {user_name}\n"
            f"📱 Телефон: `{phone_number}`\n"
            f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown'
        )
        print(f"✅ [NOTIFY] Уведомление отправлено в личный чат (ID: {MANAGER_CHAT_ID})")
    except Exception as e:
        print(f"❌ [NOTIFY] Ошибка отправки уведомления: {e}")


# === 🔥 Вебхук для Telegram ===
@app.route('/webhook', methods=['POST'])
def webhook():
    print("📡 [WEBHOOK] Получен входящий POST-запрос от Telegram")
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        print(f"❌ [WEBHOOK] КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 'Error', 500


# === ЭХО-ОБРАБОТЧИК ДЛЯ ОТЛАДКИ ===
@bot.message_handler(func=lambda message: True)
def debug_echo_handler(message):
    try:
        user_info = f"ID: {message.from_user.id}, Имя: {message.from_user.first_name}"
        print(f"📩 [ECHO] Получено сообщение от {user_info}: '{message.text}'")
        bot.reply_to(message, "🔧 [DEBUG] Бот получил ваше сообщение!")
        print("✅ [ECHO] Ответ успешно отправлен пользователю")
    except Exception as e:
        print(f"❌ [ECHO] Ошибка при отправке ответа: {e}")
        import traceback
        traceback.print_exc()


# === Автопостинг в канал ===
def send_scheduled_posts():
    """Фоновая задача: публикует посты в канале по расписанию"""
    print("⏱️ [AUTOPOST] Задача автопостинга запущена")
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
                    print(f"✅ [AUTOPOST] Пост опубликован: {title}")
                except Exception as e:
                    print(f"❌ [AUTOPOST] Ошибка отправки в канал {CHANNEL_ID}: {e}")
            conn.close()
        except Exception as e:
            print(f"❌ [AUTOPOST] Ошибка в задаче автопостинга: {e}")
        time.sleep(60)

def start_autoposting():
    thread = threading.Thread(target=send_scheduled_posts, daemon=True)
    thread.start()
    print("🧵 [AUTOPOST] Автопостинг запущен как фоновый поток")


# === Главная страница (health-check) ===
@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "BlindStyle SMM Bot Service",
        "version": "1.6",
        "message": "Bot is online. Webhook is set to /webhook"
    }), 200

# === HEAD / для Gunicorn ===
@app.route('/', methods=['HEAD'])
def head():
    return '', 200


# === Установка вебхука ===
def set_webhook():
    # 🛠 ИСПРАВЛЕНО: .strip() удаляет пробелы в начале и конце строки
    hostname = os.getenv('HOSTNAME', 'alekuk999-telegram-blinds-bot--f681.twc1.net').strip()
    # 🔥 ИСПРАВЛЕНО: УБРАН ПОРТ 8000, ИСПОЛЬЗУЕМ 443 (стандартный HTTPS)
    webhook_url = f"https://{hostname}/webhook"  # ← ПОРТ 443 ПОДРАЗУМЕВАЕТСЯ ПО УМОЛЧАНИЮ

    print(f"🔧 [WEBHOOK] Попытка установить вебхук на:{webhook_url}")

    try:
        # 🛠 ИСПРАВЛЕНО: УБРАЛИ remove_webhook() — он вызывает 404
        # result_remove = bot.remove_webhook()

        time.sleep(1)

        result_set = bot.set_webhook(url=webhook_url)
        if result_set:
            print(f"✅ [WEBHOOK] Вебхук успешно установлен:{webhook_url}")
        else:
            print(f"❌ [WEBHOOK] Метод set_webhook вернул False для URL: {webhook_url}")
    except Exception as e:
        print(f"❌ [WEBHOOK] Исключение при установке вебхука: {e}")
        import traceback
        traceback.print_exc()


# === Инициализация ===
def initialize():
    print("🔄 [INIT] Начинаем инициализацию...")
    init_db()
    add_sample_data()
    set_webhook()
    start_autoposting()
    print("✅ [INIT] Инициализация завершена.")


# 🔥🔥🔥 ВАЖНЕЙШАЯ ЧАСТЬ 🔥🔥🔥
# Вызываем initialize() СРАЗУ при импорте — это необходимо для Render + Gunicorn
initialize()

# === Запуск (Gunicorn использует эту точку входа) ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
