# wsgi.py
import asyncio
from main import app, setup_bot

# Инициализируем бота при старте
asyncio.run(setup_bot())

# Экспортируем приложение для gunicorn
application = app
