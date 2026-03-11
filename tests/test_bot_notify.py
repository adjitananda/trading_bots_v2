#!/usr/bin/env python3
"""
Тест отправки уведомления через бота
"""

import sys
from pathlib import Path
import logging

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.base_bot import TradingBot
from src.telegram.notifier import notifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Отправляем тестовое уведомление напрямую через notifier
logger.info("📨 Тест 1: Прямая отправка через notifier")
result = notifier._send(
    "🧪 Тест от bot-eth\nПрямая отправка",
    notifier.events_channel
)
print(f"Прямая отправка: {'✅' if result else '❌'}")

# Теперь попробуем создать тестовые данные сделки
logger.info("📨 Тест 2: Отправка через send_trade_notification")
test_trade = {
    'bot_id': 7,  # ID бота ETHUSDT
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
    'total_pnl': 0.0
}

result = notifier.send_trade_notification(test_trade)
print(f"Отправка через send_trade_notification: {'✅' if result else '❌'}")