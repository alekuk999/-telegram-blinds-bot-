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

CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")  # ← ЗАМЕНИ НА СВОЙ КАНАЛ!
PORT = int(os.getenv("PORT", 10000))

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

# === Путь к базе данных ===
DB_PATH = "blinds_bot.db"

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

# === Добавление тестовых данных ===
def add_sample_data():
    print("📚 [DB] Проверка и добавление тестовых данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Товары (не нужны, так как каталог по ссылкам — но оставим для совместимости)
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
        print("✅ [DB] Тестовые товары добавлены.")

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

        bot.reply_to(
            message,
            "👋 Добро пожаловать в магазин рулонных штор и жалюзи Астрахань!\n\n"
            "Выберите нужный раздел:",
            reply_markup=markup
        )
        print(f"✅ [BOT] Приветственное меню отправлено пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике /start: {e}")
        import traceback
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    try:
        print(f"🤖 [BOT] Обработчик 'Каталог' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        products = [
            {
                "name": "Рулонные шторы день-ночь",
                "desc": "Современные рулонные шторы с двумя режимами затемнения",
                "price": "2490 ₽",
                "image": "https://placehold.co/300x200/4b6cb7/white?text=День-Ночь",
                "category": "Рулонные шторы"
            },
            {
                "name": "Вертикальные жалюзи",
                "desc": "Стильные вертикальные жалюзи для больших окон",
                "price": "3290 ₽",
                "image": "https://placehold.co/300x200/182848/white?text=Вертикальные",
                "category": "Жалюзи"
            },
            {
                "name": "Горизонтальные алюминиевые жалюзи",
                "desc": "Классические жалюзи с регулировкой угла наклона",
                "price": "1890 ₽",
                "image": "https://placehold.co/300x200/3a5ca5/white?text=Алюминий",
                "category": "Жалюзи"
            },
            {
                "name": "Римские шторы",
                "desc": "Элегантные римские шторы с ручным управлением",
                "price": "3990 ₽",
                "image": "https://placehold.co/300x200/ff6b6b/white?text=Римские",
                "category": "Шторы"
            },
            {
                "name": "Рулонные шторы зебра",
                "desc": "Современные шторы зебра с чередующимися полосами",
                "price": "2790 ₽",
                "image": "https://placehold.co/300x200/27ae60/white?text=Зебра",
                "category": "Рулонные шторы"
            },
            {
                "name": "Деревянные жалюзи",
                "desc": "Натуральные деревянные жалюзи премиум класса",
                "price": "4590 ₽",
                "image": "https://placehold.co/300x200/f39c12/white?text=Дерево",
                "category": "Жалюзи"
            }
        ]

        bot.reply_to(message, "📋 Вот наш каталог товаров:")

        for p in products:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔍 Подробнее", callback_data=f"details_{p['name']}"),
                types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{p['name']}")
            )
            bot.send_photo(
                chat_id=message.chat.id,
                photo=p["image"],
                caption=f"<b>{p['name']}</b>\n{p['desc']}\n💰 {p['price']}",
                parse_mode='HTML',
                reply_markup=markup
            )

        print(f"✅ [BOT] Каталог отправлен пользователю {message.from_user.id}")

    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'Каталог': {e}")
        import traceback
        traceback.print_exc()


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
            "📞 Телефон: +7 (927) 822-29-06\n"
            "⏰ Режим работы: 9:00 — 19:00 (ежедневно)\n"
            "🏠 Адрес: г. Астрахань, ул. Ленина, д. 10, офис 5\n\n"
            "📲 Также пишите в WhatsApp: 👇\n"
            "https://wa.me/79278222906",
            parse_mode='Markdown'
        )
        print(f"✅ [BOT] Контакты отправлены пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'Контакты': {e}")
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


@bot.message_handler(func=lambda m: m.text == "💬 WhatsApp")
def open_whatsapp(message):
    try:
        print(f"🤖 [BOT] Обработчик 'WhatsApp' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        whatsapp_url = "https://wa.me/79278222906"
        bot.reply_to(
            message,
            f"💬 Напишите нам прямо сейчас в WhatsApp:\n\n{whatsapp_url}\n\n"
            "Мы ответим в течение 10 минут!",
            disable_web_page_preview=False
        )
        print(f"✅ [BOT] Ссылка на WhatsApp отправлена пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ [BOT] Ошибка в обработчике 'WhatsApp': {e}")
        import traceback
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def send_help(message):
    try:
        print(f"🤖 [BOT] Обработчик 'Помощь' вызван для пользователя {message.from_user.id}")
        save_message(message.from_user.id, message.text, True)

        help_text = (
            "📌 *Доступные функции бота*:\n\n"
            "• *Каталог* — посмотреть все товары с фото и ценами\n"
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


# === 🔥 ГЛАВНОЕ: Обработчик вебхука ===
@app.route('/webhook', methods=['POST'])
def webhook():
    print("📡 [WEBHOOK] Получен входящий POST-запрос от Telegram")
    try:
        json_str = request.get_data().decode('utf-8')
        print(f"📡 [WEBHOOK] Получены сырые данные (первые 200 символов): {json_str[:200]}...")

        update = telebot.types.Update.de_json(json_str)
        print(f"📡 [WEBHOOK] Объект Update успешно создан")

        bot.process_new_updates([update])
        print("📡 [WEBHOOK] Обновление передано боту для обработки")

        return '', 200
    except Exception as e:
        print(f"❌ [WEBHOOK] КРИТИЧЕСКАЯ ОШИБКА при обработке запроса: {e}")
        import traceback
        traceback.print_exc()
        return 'Error', 500


# === 🔍 ЭХО-ОБРАБОТЧИК ДЛЯ ОТЛАДКИ ===
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


# === Главная страница (для мониторинга и health-check) ===
@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "BlindStyle SMM Bot Service",
        "version": "1.3",
        "message": "Bot is online. Webhook is set to /webhook"
    }), 200


# === HEAD / для Gunicorn ===
@app.route('/', methods=['HEAD'])
def head():
    return '', 200


# === Установка вебхука ===
def set_webhook():
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'telegram-blinds-bot-1.onrender.com')}/webhook"
    print(f"🔧 [WEBHOOK] Попытка установить вебхук на: {webhook_url}")

    try:
        result_remove = bot.remove_webhook()
        print(f"🗑 [WEBHOOK] Старый вебхук удален: {result_remove}")

        time.sleep(1)

        result_set = bot.set_webhook(url=webhook_url)
        if result_set:
            print(f"✅ [WEBHOOK] Вебхук успешно установлен: {webhook_url}")
        else:
            print(f"❌ [WEBHOOK] Ошибка: метод set_webhook вернул False для URL: {webhook_url}")
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


# 🔥🔥🔥 ВАЖНЕЙШАЯ ЧАСТЬ — ИНИЦИАЛИЗАЦИЯ ПРИ ИМПОРТЕ
initialize()

# === Запуск (Render использует Gunicorn, этот блок игнорируется) ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
