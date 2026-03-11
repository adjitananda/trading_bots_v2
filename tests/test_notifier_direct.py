#!/usr/bin/env python3
"""
Прямой тест notifier без всего остального
"""
import os
import sys
from pathlib import Path
import logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

print("="*60)
print("ТЕСТ NOTIFIER - ПРЯМОЙ ВЫЗОВ")
print("="*60)

# Проверяем .env
from dotenv import load_dotenv
env_path = project_root / '.env'
print(f"\n1. Загружаем .env из: {env_path}")
print(f"   Файл существует: {env_path.exists()}")
load_dotenv(env_path)

# Проверяем переменные
token = os.getenv('TELEGRAM_TOKEN')
channel = os.getenv('TELEGRAM_CHANNEL_ID')
print(f"\n2. Переменные окружения:")
print(f"   TELEGRAM_TOKEN: {'✅' if token else '❌'}")
if token:
    print(f"   Token (первые 5 символов): {token[:5]}...")
print(f"   TELEGRAM_CHANNEL_ID: {channel}")

# Импортируем notifier
print(f"\n3. Импортируем notifier...")
from src.telegram.notifier import notifier
print(f"   notifier.token: {'✅' if notifier.token else '❌'}")
print(f"   notifier.events_channel: {notifier.events_channel}")

# Отправляем тестовое сообщение
print(f"\n4. Отправляем тестовое сообщение...")
test_message = f"🧪 ТЕСТОВОЕ СООБЩЕНИЕ\nВремя: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}\n\nЕсли вы это видите - notifier РАБОТАЕТ!"

result = notifier._send(test_message, notifier.events_channel)
print(f"   Результат: {'✅ УСПЕХ' if result else '❌ НЕУДАЧА'}")

print("="*60)