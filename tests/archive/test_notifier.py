#!/usr/bin/env python3
"""
Тестовый скрипт для проверки TelegramNotifier
"""

import os
import sys
from pathlib import Path

# Добавляем путь к проекту (поднимаемся на уровень выше из tests/)
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.telegram.notifier import notifier
from dotenv import load_dotenv

# Явно загружаем .env из корня проекта
env_path = project_root / '.env'
print(f"📁 Путь к .env: {env_path}")
print(f"📁 Файл существует: {env_path.exists()}")

if env_path.exists():
    load_dotenv(env_path)
    print("✅ .env загружен")
else:
    print("❌ .env НЕ НАЙДЕН!")

print("\n=== ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===")
token = os.getenv('TELEGRAM_TOKEN')
events = os.getenv('TELEGRAM_CHANNEL_ID')
logs = os.getenv('TELEGRAM_CHANNEL_ID_LOG')

print(f"TELEGRAM_TOKEN: {'✅ Загружен' if token else '❌ НЕ ЗАГРУЖЕН'}")
if token:
    print(f"  Первые 10 символов: {token[:10]}...")
print(f"TELEGRAM_CHANNEL_ID: {events}")
print(f"TELEGRAM_CHANNEL_ID_LOG: {logs}")

print("\n=== ПРОВЕРКА NOTIFIER ===")
print(f"notifier.token: {'✅ Загружен' if notifier.token else '❌ НЕ ЗАГРУЖЕН'}")
print(f"notifier.events_channel: {notifier.events_channel}")
print(f"notifier.logs_channel: {notifier.logs_channel}")

print("\n=== ТЕСТОВАЯ ОТПРАВКА ===")
if notifier.token and notifier.events_channel:
    print(f"📨 Отправка тестового сообщения в канал: {notifier.events_channel}")
    result = notifier._send(
        "🧪 Тестовое сообщение от системы\n"
        f"Время: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}",
        notifier.events_channel
    )
    print(f"Результат отправки: {'✅ УСПЕХ' if result else '❌ НЕУДАЧА'}")
else:
    print("❌ Невозможно отправить тест: нет токена или канала")
    
    # Подсказка по настройке .env
    print("\n=== КАК НАСТРОИТЬ .env ===")
    print("Добавьте в /home/trader/trading_bots_v2/.env:")
    print("""
# Telegram Bot Token (получить у @BotFather)
TELEGRAM_TOKEN=ваш_токен_бота

# ID канала для уведомлений о сделках (например @my_trading_channel или -1001234567890)
TELEGRAM_CHANNEL_ID=@your_channel

# ID канала для логов (можно тот же или отдельный)
TELEGRAM_CHANNEL_ID_LOG=@your_log_channel

# Ваш Telegram ID для доступа к командам
YOUR_TELEGRAM_ID=245799136
    """)