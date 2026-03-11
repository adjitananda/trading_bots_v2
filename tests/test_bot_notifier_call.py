#!/usr/bin/env python3
"""
Тест вызова notifier.send_trade_notification с реальными данными бота
"""
import sys
from pathlib import Path
import logging

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)

print("="*60)
print("ТЕСТ NOTIFIER С ДАННЫМИ БОТА")
print("="*60)

from src.core.database import db
from src.telegram.notifier import notifier

# Получаем реального бота
bot = db.get_bot_by_name('ETHUSDT')
print(f"\n1. Бот ETHUSDT: ID={bot['id']}, статус={bot['status']}")

# Создаём тестовые данные как в base_bot.py
test_data = {
    'bot_id': bot['id'],
    'bot_name': 'ETHUSDT',
    'symbol': 'ETHUSDT',
    'side': 'buy',
    'entry_price': 2000.0,
    'quantity': 0.01,
    'tp_price': 2040.0,
    'sl_price': 1980.0,
    'tp_percent': 2.0,
    'sl_percent': 1.0,
    'order_id': 'test_order_123',
    'balance': 1000.0,
    'symbol_pnl': 0.0,
    'total_pnl': 0.0,
    'source': 'manual'
}

print(f"\n2. Отправляем тестовые данные...")
result = notifier.send_trade_notification(test_data)
print(f"   Результат: {'✅ УСПЕХ' if result else '❌ НЕУДАЧА'}")

print("="*60)