#!/usr/bin/env python3
"""Создание тестовых данных в БД"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.utils.time_utils import now_utc
from datetime import timedelta
import random

def create_test_data():
    """Создать тестовые сделки для бота TEST_BOT"""
    
    # Получаем бота
    bot = db.get_bot_by_name('TEST_BOT')
    if not bot:
        print("❌ Бот TEST_BOT не найден")
        return
    
    bot_id = bot['id']
    exchange_id = bot['exchange_id']
    
    print(f"📊 Создаем тестовые данные для бота ID: {bot_id}")
    
    # Создаем несколько тестовых сделок
    test_trades = [
        {
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'entry_price': 50000,
            'exit_price': 51000,
            'quantity': 0.01,
            'pnl': 10.0
        },
        {
            'symbol': 'ETHUSDT',
            'side': 'BUY',
            'entry_price': 3000,
            'exit_price': 3100,
            'quantity': 0.1,
            'pnl': 10.0
        },
        {
            'symbol': 'SOLUSDT',
            'side': 'BUY',
            'entry_price': 100,
            'exit_price': 95,
            'quantity': 1,
            'pnl': -5.0
        }
    ]
    
    now = now_utc()
    
    for trade in test_trades:
        # Создаем сделку
        trade_id = db.create_trade({
            'bot_id': bot_id,
            'exchange_id': exchange_id,
            'symbol': trade['symbol'],
            'side': trade['side'],
            'entry_time': now - timedelta(hours=random.randint(1, 24)),
            'entry_price': trade['entry_price'],
            'quantity': trade['quantity'],
            'entry_order_id': f"test_order_{random.randint(1000, 9999)}"
        })
        
        # Закрываем сделку
        db.close_trade(trade_id, {
            'exit_time': now,
            'exit_price': trade['exit_price'],
            'pnl': trade['pnl'],
            'pnl_percent': ((trade['exit_price'] - trade['entry_price']) / trade['entry_price']) * 100,
            'exit_reason': 'TP' if trade['pnl'] > 0 else 'SL',
            'exit_order_id': f"test_exit_{random.randint(1000, 9999)}"
        })
        
        print(f"  ✅ Создана сделка {trade['symbol']}: {trade['pnl']} USDT")
    
    print("\n✅ Тестовые данные созданы!")

if __name__ == "__main__":
    create_test_data()