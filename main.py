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

# === Добавление тестовых данных (если пусто) ===
def add_sample_data():
    print("📚 [DB] Проверка и добавление тестовых данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ("Рулонные шторы день-ночь", "Современные рулонные шторы с двумя режимами затемнения: светлый и тёмный. Идеально для спальни и гостиной.", 2490.0, "Рулонные шторы", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Вертикальные жалюзи из ткани", "Элегантные вертикальные жалюзи из плотной ткани. Регулируемый свет и полная конфиденциальность.", 3290.0, "Жалюзи", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Горизонтальные алюминиевые жалюзи", "Классические алюминиевые жалюзи с поворотом ламелей. Легко моются, подходят для кухни и ванной.", 1890.0, "Жалюзи", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Римские шторы с ламбрекеном", "Шикарные римские шторы с декоративным ламбрекеном. Подчеркнут ваш интерьер в стиле лофт или скандинавия.", 3990.0, "Шторы", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Рулонные шторы зебра", "Современный дизайн с чередующимися полосами белого и серого. Дневной и ночной режим в одной шторе.", 2790.0, "Рулонные шторы", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Деревянные жалюзи премиум", "Натуральное дерево — дуб и орех. Тепло, экологично, долговечно. Подходит для офиса и дома.", 4590.0, "Жалюзи", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Рулонные шторы \"Туман\"", "Полупрозрачные шторы с эффектом мягкого рассеивания света. Идеальны для детской и рабочего кабинета.", 2190.0, "Рулонные шторы", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Жалюзи \"Бамбук\"", "Эко-жалюзи из натурального бамбука. Природная текстура, уют, тишина. Для спальни и террасы.", 3790.0, "Жалюзи", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Римские шторы с подсветкой", "Умные римские шторы со встроенной LED-подсветкой по контуру. Управление через приложение или пульт.", 5990.0, "Шторы", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg"),
            ("Рулонные шторы \"Мрамор\"", "Имитация мраморного узора на ткани. Роскошь без лишних затрат. Для элитных интерьеров.", 3490.0, "Рулонные шторы", "https://i.ibb.co/6YfGvKk/rulonnye-katalog.jpg")
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

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, price, image_url FROM products WHERE image_url IS NOT NULL AND image_url != ''")
        products = cursor.fetchall()
        conn.close()

        if not products:
            bot.reply_to(message, "📦 Каталог временно пуст. Пожалуйста, свяжитесь с нами по телефону.")
            print("⚠️ [CATALOG] В базе нет товаров с картинками.")
            return

        bot.reply_to(message, "📋 Вот наш актуальный каталог:")

        for product in products:
            name, desc, price, image_url = product
            price_formatted = f"{price:.2f} ₽" if isinstance(price, float) else str(price)

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔍 Подробнее", callback_data=f"details_{name}"),
                types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{name}")
            )

            bot.send_photo(
                chat_id=message.chat.id,
                photo=image_url,
                caption=f"<b>{name}</b>\n{desc}\n💰 {price_formatted}",
                parse_mode='HTML',
                reply_markup=markup
            )

        print(f"✅ [CATALOG] Отправлено {len(products)} товаров пользователю {message.from_user.id}")

    except Exception as e:
        print(f"❌ [CATALOG] Ошибка при загрузке каталога: {e}")
        import traceback
        traceback.print_exc()
        bot.reply_to(message, "❌ Произошла ошибка при загрузке каталога. Попробуйте позже.")


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
            "https://wa.me/+79278222906",
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
        "version": "1.4",
        "message": "Bot is online. Webhook is set to /webhook"
    }), 200

# === HEAD / для Gunicorn ===
@app.route('/', methods=['HEAD'])
def head():
    return '', 200


# === Установка вебхука ===
def set_webhook():
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/webhook"
    if "localhost" in webhook_url:
        webhook_url = "https://telegram-blinds-bot-1.onrender.com/webhook"  # ← ЗАМЕНИ НА СВОЙ ДОМЕН!

    print(f"🔧 [WEBHOOK] Попытка установить вебхук на: {webhook_url}")

    try:
        result_remove = bot.remove_webhook()
        print(f"🗑 [WEBHOOK] Старый вебхук удален: {result_remove}")

        time.sleep(1)

        result_set = bot.set_webhook(url=webhook_url)
        if result_set:
            print(f"✅ [WEBHOOK] Вебхук успешно установлен: {webhook_url}")
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
