from flask import Flask, request, jsonify
import telebot
from telebot import types
import sqlite3
from datetime import datetime
import threading
import os
import random

app = Flask(__name__)

# Конфигурация бота - используем переменные окружения для Render
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://your-app-name.onrender.com')
bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    
    # Таблица для товаров
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
    
    # Таблица для заказов
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
    
    # Таблица для пользователей
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
    
    # Таблица для сообщений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            is_from_user BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица для SMM контента
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
    
    # Таблица для подписчиков канала
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

# Добавление тестовых данных
def add_sample_data():
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, есть ли уже данные товаров
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        # Добавляем тестовые товары
        products = [
            ("Рулонные шторы день-ночь", "Современные рулонные шторы с двумя режимами затемнения", 2490.0, "Рулонные шторы", "https://placehold.co/300x200/4b6cb7/white?text=День-Ночь"),
            ("Вертикальные жалюзи", "Стильные вертикальные жалюзи для больших окон", 3290.0, "Жалюзи", "https://placehold.co/300x200/182848/white?text=Вертикальные"),
            ("Горизонтальные алюминиевые жалюзи", "Классические жалюзи с регулировкой угла наклона", 1890.0, "Жалюзи", "https://placehold.co/300x200/3a5ca5/white?text=Алюминий"),
            ("Римские шторы", "Элегантные римские шторы с ручным управлением", 3990.0, "Шторы", "https://placehold.co/300x200/ff6b6b/white?text=Римские"),
            ("Рулонные шторы зебра", "Современные шторы зебра с чередующимися полосами", 2790.0, "Рулонные шторы", "https://placehold.co/300x200/27ae60/white?text=Зебра"),
            ("Деревянные жалюзи", "Натуральные деревянные жалюзи премиум класса", 4590.0, "Жалюзи", "https://placehold.co/300x200/f39c12/white?text=Дерево")
        ]
        
        cursor.executemany(
            "INSERT INTO products (name, description, price, category, image_url) VALUES (?, ?, ?, ?, ?)",
            products
        )
    
    # Проверяем, есть ли уже SMM контент
    cursor.execute("SELECT COUNT(*) FROM smm_content")
    if cursor.fetchone()[0] == 0:
        # Добавляем тестовый SMM контент
        smm_content = [
            ("5 причин выбрать рулонные шторы", "Рулонные шторы - идеальное решение для современного интерьера. Они практичны, красивы и функциональны!", "https://placehold.co/600x400/4b6cb7/white?text=Рулонные+шторы", "Образование", None, 1),
            ("Как выбрать жалюзи для кухни", "Кухня требует особого подхода к выбору жалюзи. Рассказываем, на что обратить внимание!", "https://placehold.co/600x400/182848/white?text=Жалюзи+для+кухни", "Советы", None, 1),
            ("Тренды 2023: Что в моде у штор", "Следите за модой и в интерьере! Рассказываем о главных трендах в мире штор этого года.", "https://placehold.co/600x400/ff6b6b/white?text=Тренды+2023", "Тренды", None, 1),
            ("Сравнение материалов: Ткань vs ПВХ", "Какой материал выбрать для рулонных штор? Разбираемся в плюсах и минусах каждого варианта.", "https://placehold.co/600x400/27ae60/white?text=Материалы", "Образование", None, 1),
            ("Дизайн спальни с идеальными шторами", "Создайте уютную атмосферу в спальне с помощью правильно подобранных штор!", "https://placehold.co/600x400/f39c12/white?text=Дизайн+спальни", "Дизайн", None, 1)
        ]
        
        cursor.executemany(
            "INSERT INTO smm_content (title, content, image_url, category, scheduled_time, is_published) VALUES (?, ?, ?, ?, ?, ?)",
            smm_content
        )
    
    conn.commit()
    conn.close()

# Обработчики команд бота
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Сохраняем пользователя в базу
    save_user(message.from_user)
    
    # Сохраняем сообщение
    save_message(message.from_user.id, message.text, True)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍 Каталог", "🎯 Заказать")
    markup.add("📢 Канал", "📞 Контакты")
    markup.add("ℹ️ О нас", "📚 Полезное")
    
    welcome_text = """
🌟 Добро пожаловать в BlindStyle!

Мы создаем уют и комфорт в вашем доме с помощью:
• ✨ Красивых жалюзи и штор
• 📏 Точного замера
• 🛠 Профессионального монтажа

Выберите интересующий раздел:
    """
    
    bot.reply_to(message, welcome_text, reply_markup=markup)

@bot.message_handler(commands=['help'])
def send_help(message):
    save_message(message.from_user.id, message.text, True)
    
    help_text = """
🤖 Доступные команды:
/start - Главное меню
/catalog - Каталог товаров
/order - Оформить заказ
/channel - Наш Telegram канал
/contact - Контакты
/about - О компании
/help - Помощь

Используйте кнопки внизу экрана для навигации!
    """
    
    bot.reply_to(message, help_text)

@bot.message_handler(func=lambda message: message.text == "🛍 Каталог")
def show_catalog(message):
    save_message(message.from_user.id, message.text, True)
    
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    
    if products:
        # Отправляем приветственное сообщение перед каталогом
        bot.reply_to(message, "📋 Наш каталог товаров:")
        
        for product in products:
            markup = types.InlineKeyboardMarkup()
            order_btn = types.InlineKeyboardButton(
                "🛒 Заказать", 
                callback_data=f"order_{product[0]}"
            )
            details_btn = types.InlineKeyboardButton(
                "🔍 Подробнее", 
                callback_data=f"details_{product[0]}"
            )
            markup.add(details_btn, order_btn)
            
            product_text = f"""
<b>{product[1]}</b>

{product[2]}

💰 <b>Цена: {product[3]:.2f} руб.</b>

🏷 Категория: {product[4]}
            """
            
            try:
                bot.send_photo(
                    message.chat.id, 
                    product[5], 
                    caption=product_text, 
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except:
                # Если фото не отправляется, отправляем текст
                bot.send_message(
                    message.chat.id, 
                    product_text, 
                    parse_mode='HTML',
                    reply_markup=markup
                )
    else:
        bot.reply_to(message, "📋 Каталог временно пуст. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.text == "🎯 Заказать")
def start_order(message):
    save_message(message.from_user.id, message.text, True)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍 Каталог")
    markup.add("⬅️ Назад")
    
    bot.reply_to(message, "Для оформления заказа выберите товар из каталога.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📢 Канал")
def show_channel(message):
    save_message(message.from_user.id, message.text, True)
    
    # Добавляем пользователя в подписчики
    save_subscriber(message.from_user)
    
    channel_text = """
📢 Наш Telegram канал - источник полезной информации!

Подписывайтесь, чтобы получать:
• 💡 Лайфхаки по выбору жалюзи
• 🎨 Идеи дизайна интерьера
• 🎁 Специальные предложения
• 📚 Обучающие материалы

Ссылка на канал: @blindstyle_channel
(Канал для примера - создайте свой!)
    """
    
    markup = types.InlineKeyboardMarkup()
    channel_btn = types.InlineKeyboardButton(
        "🔗 Перейти в канал", 
        url="https://t.me/blindstyle_channel"
    )
    markup.add(channel_btn)
    
    bot.reply_to(message, channel_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📞 Контакты")
def show_contacts(message):
    save_message(message.from_user.id, message.text, True)
    
    contacts_text = """
📞 Наши контакты:

🏪 Магазин "BlindStyle"
📍 Москва, ул. Примерная, 15
🚇 Метро: Примерная станция
⏰ Пн-Вс 10:00-20:00

📱 Телефон: +7 (495) 123-45-67
📧 Email: info@blindstyle.ru
🌐 Сайт: www.blindstyle.ru

💬 Telegram: @blindstyle_manager
    """
    
    markup = types.InlineKeyboardMarkup()
    contact_btn = types.InlineKeyboardButton(
        "📞 Позвонить", 
        url="tel:+74951234567"
    )
    markup.add(contact_btn)
    
    bot.reply_to(message, contacts_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "ℹ️ О нас")
def show_about(message):
    save_message(message.from_user.id, message.text, True)
    
    about_text = """
 blinds и штор с 2010 года!

🏆 Почему выбирают нас:
• ✅ 13 лет опыта
• 👥 1000+ довольных клиентов
• 🛡 Гарантия 3 года
• 🎁 Бесплатная консультация
• 🚚 Быстрая доставка
• 🔧 Профи монтаж

🛠 Наши услуги:
• 📏 Замер окон
• 🏭 Изготовление под заказ
• 🛠 Установка и монтаж
• 🔧 Ремонт и обслуживание

Используем качественные материалы от проверенных поставщиков.
    """
    
    bot.reply_to(message, about_text)

@bot.message_handler(func=lambda message: message.text == "📚 Полезное")
def show_useful(message):
    save_message(message.from_user.id, message.text, True)
    
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM smm_content WHERE is_published = 1 ORDER BY created_at DESC LIMIT 5")
    content_list = cursor.fetchall()
    conn.close()
    
    if content_list:
        bot.reply_to(message, "📚 Полезные материалы для вас:")
        
        for content in content_list:
            content_text = f"""
<b>{content[1]}</b>

{content[2]}

#{content[4].replace(' ', '_')}
            """
            
            try:
                bot.send_photo(
                    message.chat.id, 
                    content[3], 
                    caption=content_text, 
                    parse_mode='HTML'
                )
            except:
                bot.send_message(
                    message.chat.id, 
                    content_text, 
                    parse_mode='HTML'
                )
    else:
        bot.reply_to(message, "📚 Полезных материалов пока нет. Следите за обновлениями!")

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад")
def go_back(message):
    save_message(message.from_user.id, message.text, True)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍 Каталог", "🎯 Заказать")
    markup.add("📢 Канал", "📞 Контакты")
    markup.add("ℹ️ О нас", "📚 Полезное")
    
    bot.reply_to(message, "Выберите интересующий раздел:", reply_markup=markup)

# Обработчики callback'ов
@bot.callback_query_handler(func=lambda call: call.data.startswith('order_'))
def handle_order(call):
    product_id = int(call.data.split('_')[1])
    
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if product:
        bot.answer_callback_query(call.id, "Оформление заказа...")
        
        order_text = f"""
🛒 Оформление заказа на товар:

<b>{product[0]}</b>

💰 Цена: {product[1]:.2f} руб.

Для оформления заказа, пожалуйста, отправьте свои контактные данные:
1. Ваше имя
2. Номер телефона
3. Адрес для доставки
        """
        
        msg = bot.send_message(call.message.chat.id, order_text, parse_mode='HTML')
        bot.register_next_step_handler(msg, process_order_step1, product_id, product)

def process_order_step1(message, product_id, product):
    save_message(message.from_user.id, message.text, True)
    
    user_data = {
        'product_id': product_id,
        'product_name': product[0],
        'user_name': message.text
    }
    
    msg = bot.reply_to(message, "📱 Пожалуйста, введите ваш номер телефона:")
    bot.register_next_step_handler(msg, process_order_step2, user_data)

def process_order_step2(message, user_data):
    save_message(message.from_user.id, message.text, True)
    
    user_data['phone'] = message.text
    
    msg = bot.reply_to(message, "📍 Введите адрес для доставки:")
    bot.register_next_step_handler(msg, process_order_step3, user_data)

def process_order_step3(message, user_data):
    save_message(message.from_user.id, message.text, True)
    
    user_data['address'] = message.text
    
    # Сохраняем заказ в базу
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_id, product_id, user_name, phone, address)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        message.from_user.id,
        user_data['product_id'],
        user_data['user_name'],
        user_data['phone'],
        user_data['address']
    ))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    
    # Отправляем подтверждение пользователю
    confirmation_text = f"""
✅ Заказ оформлен!

🆔 Номер заказа: #{order_id}
🛍 Товар: {user_data['product_name']}
👤 Имя: {user_data['user_name']}
📱 Телефон: {user_data['phone']}
📍 Адрес: {user_data['address']}

Наш менеджер свяжется с вами в течение 15 минут!

Спасибо за выбор BlindStyle! 🙏
    """
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍 Каталог", "🎯 Заказать")
    markup.add("📢 Канал", "📞 Контакты")
    markup.add("ℹ️ О нас", "📚 Полезное")
    
    bot.reply_to(message, confirmation_text, reply_markup=markup)
    
    # Отправляем уведомление администратору
    admin_notification = f"""
🔔 НОВЫЙ ЗАКАЗ!

🆔 Номер заказа: #{order_id}
🛍 Товар: {user_data['product_name']}
👤 Клиент: {user_data['user_name']}
📱 Телефон: {user_data['phone']}
📍 Адрес: {user_data['address']}
🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    print(admin_notification)  # Для демонстрации на Render

@bot.callback_query_handler(func=lambda call: call.data.startswith('details_'))
def handle_details(call):
    product_id = int(call.data.split('_')[1])
    
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if product:
        details_text = f"""
<b>{product[1]}</b>

{product[2]}

💰 <b>Цена: {product[3]:.2f} руб.</b>
🏷 Категория: {product[4]}

📏 Рекомендации:
• Измеряйте окно точно
• Учитывайте тип крепления
• Выбирайте по помещению

🔧 Установка:
• Профи установка в подарок
• Самовывоз по договоренности

🚚 Доставка:
• Бесплатно от 5000 руб.
• Срочно за 24 часа
        """
        
        markup = types.InlineKeyboardMarkup()
        order_btn = types.InlineKeyboardButton(
            "🛒 Заказать", 
            callback_data=f"order_{product[0]}"
        )
        markup.add(order_btn)
        
        try:
            bot.edit_message_caption(
                caption=details_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='HTML',
                reply_markup=markup
            )
        except:
            bot.send_message(
                call.message.chat.id,
                details_text,
                parse_mode='HTML',
                reply_markup=markup
            )

# Обработчик всех остальных сообщений
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    save_message(message.from_user.id, message.text, True)
    
    response_text = """
🤔 Не понимаю команду.

Используйте меню для навигации:
🛍 Каталог - просмотр товаров
🎯 Заказать - создание заказа
📢 Канал - полезный контент
📞 Контакты - наши реквизиты
ℹ️ О нас - информация о компании
📚 Полезное - советы и статьи
    """
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍 Каталог", "🎯 Заказать")
    markup.add("📢 Канал", "📞 Контакты")
    markup.add("ℹ️ О нас", "📚 Полезное")
    
    bot.reply_to(message, response_text, reply_markup=markup)

# Функции для работы с базой данных
def save_user(user):
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, registered_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении пользователя: {e}")
    finally:
        conn.close()

def save_subscriber(user):
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO subscribers 
            (user_id, username, first_name, last_name, subscribed_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении подписчика: {e}")
    finally:
        conn.close()

def save_message(user_id, text, is_from_user):
    conn = sqlite3.connect('blinds_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO messages (user_id, message, is_from_user, created_at)
            VALUES (?, ?, ?, ?)
        ''', (
            user_id,
            text,
            is_from_user,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении сообщения: {e}")
    finally:
        conn.close()

# API эндпоинты для SMM и мониторинга
@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "service": "BlindStyle SMM Bot Service",
        "version": "1.0"
    })

@app.route('/api/stats')
def get_stats():
    try:
        conn = sqlite3.connect('blinds_bot.db')
        cursor = conn.cursor()
        
        # Количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        
        # Количество подписчиков канала
        cursor.execute("SELECT COUNT(*) FROM subscribers")
        subscribers_count = cursor.fetchone()[0]
        
        # Количество заказов сегодня
        cursor.execute("""
            SELECT COUNT(*) FROM orders 
            WHERE DATE(created_at) = DATE('now')
        """)
        orders_today = cursor.fetchone()[0]
        
        # Новые сообщения
        cursor.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE is_from_user = 1 AND DATE(created_at) = DATE('now')
        """)
        new_messages = cursor.fetchone()[0]
        
        # Количество опубликованного контента
        cursor.execute("SELECT COUNT(*) FROM smm_content WHERE is_published = 1")
        content_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'users': users_count,
            'subscribers': subscribers_count,
            'orders_today': orders_today,
            'new_messages': new_messages,
            'content_count': content_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/orders')
def get_orders():
    try:
        conn = sqlite3.connect('blinds_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT o.id, o.user_name, o.phone, o.address, o.status, o.created_at, p.name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            ORDER BY o.created_at DESC
            LIMIT 20
        """)
        
        orders = cursor.fetchall()
        conn.close()
        
        orders_list = []
        for order in orders:
            orders_list.append({
                'id': order[0],
                'user_name': order[1],
                'phone': order[2],
                'address': order[3],
                'status': order[4],
                'created_at': order[5],
                'product_name': order[6]
            })
        
        return jsonify(orders_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/messages')
def get_messages():
    try:
        conn = sqlite3.connect('blinds_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.id, m.message, m.created_at, u.first_name, u.last_name
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            WHERE m.is_from_user = 1
            ORDER BY m.created_at DESC
            LIMIT 20
        """)
        
        messages = cursor.fetchall()
        conn.close()
        
        messages_list = []
        for message in messages:
            messages_list.append({
                'id': message[0],
                'text': message[1],
                'created_at': message[2],
                'user_name': f"{message[3] or ''} {message[4] or ''}".strip()
            })
        
        return jsonify(messages_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/products')
def get_products():
    try:
        conn = sqlite3.connect('blinds_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
        conn.close()
        
        products_list = []
        for product in products:
            products_list.append({
                'id': product[0],
                'name': product[1],
                'description': product[2],
                'price': product[3],
                'category': product[4],
                'image_url': product[5]
            })
        
        return jsonify(products_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/content')
def get_content():
    try:
        conn = sqlite3.connect('blinds_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM smm_content WHERE is_published = 1 ORDER BY created_at DESC")
        content = cursor.fetchall()
        conn.close()
        
        content_list = []
        for item in content:
            content_list.append({
                'id': item[0],
                'title': item[1],
                'content': item[2],
                'image_url': item[3],
                'category': item[4],
                'scheduled_time': item[5],
                'is_published': bool(item[6]),
                'created_at': item[7]
            })
        
        return jsonify(content_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/subscribers')
def get_subscribers():
    try:
        conn = sqlite3.connect('blinds_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM subscribers ORDER BY subscribed_at DESC")
        subscribers = cursor.fetchall()
        conn.close()
        
        subscribers_list = []
        for subscriber in subscribers:
            subscribers_list.append({
                'id': subscriber[0],
                'user_id': subscriber[1],
                'username': subscriber[2],
                'first_name': subscriber[3],
                'last_name': subscriber[4],
                'subscribed_at': subscriber[5]
            })
        
        return jsonify(subscribers_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Message.de_json(json_str)
    bot.process_new_messages([update])
    return 'OK', 200

# Функция для установки вебхука
def set_webhook():
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"Webhook установлен: {webhook_url}")
    except Exception as e:
        print(f"Ошибка установки webhook: {e}")

# Инициализация при запуске
def initialize_app():
    init_db()
    add_sample_data()
    set_webhook()

if __name__ == '__main__':
    # Инициализация приложения
    initialize_app()
    
    # Получаем порт из переменных окружения Render или используем 5000 по умолчанию
    port = int(os.environ.get('PORT', 5000))
    
    # Запуск Flask приложения
    app.run(host='0.0.0.0', port=port, debug=False)
