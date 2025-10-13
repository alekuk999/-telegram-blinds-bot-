import os
import re
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
MANAGER_CHAT_ID = 7126605143  # ← Убедитесь, что это ваш реальный ID

_INITIALIZED = False

# === Вспомогательная функция: проверка номера ===
def is_valid_phone(phone: str) -> bool:
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('7'):
        return True
    if len(digits) == 10 and digits.startswith('9'):
        return True
    return False

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

# === Добавление тестовых данных ===
def add_sample_data():
    print("📚 [DB] Проверка и добавление тестовых данных...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ("Рулонные шторы день-ночь", "✨ *Идеально для спальни и гостиной!*...", 0.0, "Рулонные шторы", "images/rulonnye_den_noch.jpg"),
            ("Рулонные шторы зебра", "🎨 *Современный дизайн с эффектом зебры!*...", 0.0, "Рулонные шторы", "images/rulonnye_zebra.jpg"),
            ("Рулонные шторы блэкаут", "🌙 *Полное затемнение для комфортного сна!*...", 0.0, "Рулонные шторы", "images/rulonnye_blackout.jpg"),
            ("Горизонтальные жалюзи алюминиевые", "🔧 *Классика, проверенная временем!*...", 0.0, "Горизонтальные жалюзи", "images/gorizontalnye_aluminievye.jpg"),
            ("Горизонтальные жалюзи деревянные", "🪵 *Натуральная эстетика и экологичность!*...", 0.0, "Горизонтальные жалюзи", "images/gorizontalnye_derevyannye.jpg"),
            ("Вертикальные жалюзи тканевые", "🌿 *Элегантность и уют в вашем доме!*...", 0.0, "Вертикальные жалюзи", "images/vertikalnye_tkanevye.jpg"),
            ("Вертикальные жалюзи ПВХ", "💧 *Практично и бюджетно!*...", 0.0, "Вертикальные жалюзи", "images/vertikalnye_pvh.jpg"),
            ("Жалюзи плиссе тканевые", "🎨 *Изысканный дизайн для нестандартных окон!*...", 0.0, "Жалюзи плиссе", "images/plisse_tkanevye.jpg"),
            ("Жалюзи плиссе алюминиевые", "🪟 *Современно и функционально!*...", 0.0, "Жалюзи плиссе", "images/plisse_aluminievye.jpg"),
            ("Деревянные жалюзи дуб", "🌳 *Натуральная роскошь и статус!*...", 0.0, "Деревянные жалюзи", "images/derevyannye_dub.jpg"),
            ("Деревянные жалюзи орех", "🌰 *Тёплый и уютный интерьер!*...", 0.0, "Деревянные жалюзи", "images/derevyannye_orekh.jpg"),
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
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)', 
                       (user.id, user.username, user.first_name, user.last_name))
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

# === Главное меню ===
def show_main_menu(message, custom_text=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Каталог", "🧵 Ткани")
    markup.add("🔗 Канал", "📞 Контакты")
    markup.add("💬 WhatsApp", "ℹ️ Помощь")
    text = custom_text or "👇 Выберите нужный раздел:"
    bot.send_message(message.chat.id, text, reply_markup=markup)

# === /start ===
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
            "• 🧵 Выбрать ткань из 8 категорий\n"
            "• 📞 Заказать бесплатный замер или звонок менеджера\n"
            "• 🔗 Перейти в наш Telegram-канал\n"
            "• 💬 Написать нам в WhatsApp или Telegram\n\n"
            "👇 Выберите нужный раздел:"
        )
        show_main_menu(message, welcome_text)
    except Exception as e:
        print(f"❌ [BOT] Ошибка в /start: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Попробуйте позже.")

# === Каталог ===
@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def show_catalog(message):
    save_message(message.from_user.id, message.text, True)
    markup = types.InlineKeyboardMarkup(row_width=1)
    cats = [
        ("🧵 Рулонные шторы", "Рулонные шторы"),
        ("🪟 Горизонтальные жалюзи", "Горизонтальные жалюзи"),
        ("🚪 Вертикальные жалюзи", "Вертикальные жалюзи"),
        ("🌀 Жалюзи плиссе", "Жалюзи плиссе"),
        ("🪵 Деревянные жалюзи", "Деревянные жалюзи"),
    ]
    for label, cat in cats:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"category_{cat}"))
    markup.add(types.InlineKeyboardButton("💬 Написать в WhatsApp", url="https://wa.me/79378222906"))
    markup.add(types.InlineKeyboardButton("📞 Заказать звонок", callback_data="request_call"))
    bot.reply_to(message, "✨ *Выберите категорию товаров:*", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    category = call.data.split('_', 1)[1]
    bot.answer_callback_query(call.id)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, image_url FROM products WHERE category = ?", (category,))
    products = cursor.fetchall()
    conn.close()
    if not products:
        bot.send_message(call.message.chat.id, f"📦 В категории *{category}* пока нет товаров.", parse_mode='Markdown')
        return
    bot.send_message(call.message.chat.id, f"📋 *Товары в категории: {category}*", parse_mode='Markdown')
    for name, desc, image_url in products:
        product_key = hashlib.md5(name.encode()).hexdigest()[:8]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔍 Подробнее", callback_data=f"details_{product_key}"),
            types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{product_key}")
        )
        try:
            with open(image_url, 'rb') as f:
                bot.send_photo(call.message.chat.id, f, caption=f"<b>{name}</b>\n{desc}", parse_mode='HTML', reply_markup=markup)
        except:
            bot.send_message(call.message.chat.id, f"❌ Фото для '{name}' не найдено.")
    show_main_menu(call.message)

# === Ткани ===
@bot.message_handler(func=lambda m: m.text == "🧵 Ткани")
def show_fabric_categories(message):
    categories = ["зебра", "рулонка", "плиссе", "вертикальные", "вертикальные пластик", "дерево50", "дерево25мм", "алюминий25мм"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(*[types.InlineKeyboardButton(cat, callback_data=f"fabric:{cat}") for cat in categories])
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
        show_fabric_samples(call.message, category, offset=int(offset_str))
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "❌ Ошибка загрузки. Попробуйте снова.")

def show_fabric_samples(message, category, offset=0, batch_size=10):
    folder_map = {
        "зебра": "zebra", "рулонка": "rulonka", "плиссе": "plisse",
        "вертикальные": "vertikalnye", "вертикальные пластик": "vertikalnye_plastik",
        "дерево50": "derevo50", "дерево25мм": "derevo25mm", "алюминий25мм": "alyuminij25mm"
    }
    folder = folder_map.get(category)
    if not folder or not os.path.exists(f"fabric-samples/{folder}"):
        bot.send_message(message.chat.id, "❌ Категория не найдена.")
        return
    files = sorted(f for f in os.listdir(f"fabric-samples/{folder}") if f.lower().endswith('.jpg'))
    if not files:
        bot.send_message(message.chat.id, f"В категории '{category}' нет образцов.")
        return
    for f in files[offset:offset+batch_size]:
        try:
            name = os.path.splitext(f)[0].replace("_", " ").title()
            with open(f"fabric-samples/{folder}/{f}", 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=f"• *{category}*\n• Артикул: `{name}`", parse_mode='Markdown')
        except Exception as e:
            print(f"❌ Ошибка отправки {f}: {e}")
    if offset + batch_size < len(files):
        markup = types.InlineKeyboardMarkup()
        cb = f"fabric_next:{category}:{offset+batch_size}"
        if len(cb) > 64: cb = cb[:60] + "..."
        markup.add(types.InlineKeyboardButton("➡️ Показать ещё", callback_data=cb))
        bot.send_message(message.chat.id, f"Показано {min(offset+batch_size, len(files))} из {len(files)}", reply_markup=markup)

# === Прочие команды ===
@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def show_contacts(message):
    bot.reply_to(message, 
        "📍 *Контактная информация:*\n\n"
        "📞 Телефон: +7 (937) 822-29-06\n"
        "💬 WhatsApp: [Написать](https://wa.me/79378222906)\n"
        "✉️ Telegram: [Написать менеджеру](https://t.me/astra_jalyzi30)\n"
        "⏰ Режим работы: 9:00 — 19:00\n"
        "🏠 Адрес: г. Астрахань, ул. Ленина, д. 10, офис 5",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "💬 WhatsApp")
def open_whatsapp(message):
    bot.reply_to(message, "💬 Напишите нам в WhatsApp:\nhttps://wa.me/79378222906",
        reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("📲 Открыть чат", url="https://wa.me/79378222906")]]))

@bot.message_handler(func=lambda m: m.text == "🔗 Канал")
def open_channel(message):
    bot.reply_to(message, f"📢 Наш Telegram-канал:\n{CHANNEL_ID}")

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def send_help(message):
    bot.reply_to(message, 
        "📌 *Доступные функции бота:*\n\n"
        "• *Каталог* — посмотреть все товары\n"
        "• *Ткани* — выбрать материал\n"
        "• *Контакты* — узнать адрес и телефон\n"
        "• *Канал* — новости и акции\n"
        "• *WhatsApp* — написать мгновенно\n\n"
        "💡 Все запросы обрабатываются вручную — перезваниваем в течение 15 минут!",
        parse_mode='Markdown'
    )

# === ЗАКАЗ ЗВОНКА С ОТМЕНОЙ ===
@bot.callback_query_handler(func=lambda call: call.data == "request_call")
def request_call_handler(call):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📲 Отправить мой номер", request_contact=True))
    markup.add("↩️ Отмена")
    msg = bot.send_message(
        call.message.chat.id,
        "📞 *Пожалуйста, отправьте ваш номер телефона*, и мы перезвоним вам в течение 5 минут!\n\n"
        "📱 Вы можете:\n"
        "• Нажать «Отправить мой номер»\n"
        "• Ввести номер вручную (например: `+79271234567`)\n"
        "• Или нажать «↩️ Отмена»",
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, process_phone_number, call.from_user.first_name)

def process_phone_number(message, user_name):
    # Обработка отмены
    if message.text == "↩️ Отмена":
        bot.send_message(message.chat.id, "📞 Запрос отменён.", reply_markup=types.ReplyKeyboardRemove())
        show_main_menu(message)
        return

    phone = None
    if message.contact:
        phone = message.contact.phone_number
    else:
        raw = message.text.strip()
        if is_valid_phone(raw):
            digits = re.sub(r'\D', '', raw)
            phone = '7' + digits[-10:] if len(digits) == 10 else digits

    if not phone:
        bot.send_message(
            message.chat.id,
            "❌ Это не похоже на номер телефона. Попробуйте ещё раз или нажмите «↩️ Отмена».",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_main_menu(message)
        return

    # Сохранение и уведомление
    save_call_request(message.from_user.id, user_name, phone)
    notify_manager(user_name, phone)

    bot.send_message(
        message.chat.id,
        f"✅ Спасибо, {user_name}!\n\nМы получили ваш номер: `{phone}`\n📞 Менеджер перезвонит вам в течение 5 минут!",
        parse_mode='Markdown',
        reply_markup=types.ReplyKeyboardRemove()
    )
    show_main_menu(message)

def save_call_request(user_id, first_name, phone_number):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO orders (user_id, user_name, phone, status) VALUES (?, ?, ?, ?)',
                       (user_id, first_name, phone_number, "pending"))
        conn.commit()
    except Exception as e:
        print(f"❌ Ошибка сохранения заявки: {e}")
    finally:
        conn.close()

def notify_manager(user_name, phone_number):
    try:
        bot.send_message(
            MANAGER_CHAT_ID,
            f"🔔 *Новая заявка на звонок!*\n\n👤 Имя: {user_name}\n📱 Телефон: `{phone_number}`\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ Не удалось уведомить менеджера: {e}")

# === Flask + Webhook ===
@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
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
