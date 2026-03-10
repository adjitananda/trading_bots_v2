#!/usr/bin/env python3
"""
Тест синхронизации ордеров между биржей и БД
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.trading.exchange_client import ExchangeFactory


def test_orders_sync(bot_name='TEST_BOT'):
    """Проверка синхронизации ордеров"""
    
    bot = db.get_bot_by_name(bot_name)
    if not bot:
        print(f"❌ Бот {bot_name} не найден")
        return
    
    exchange = ExchangeFactory.create_client_for_bot(bot_name)
    
    print(f"\n📋 ТЕСТ СИНХРОНИЗАЦИИ ОРДЕРОВ")
    print("=" * 60)
    
    # Получаем ордера из БД за последние 24 часа
    query = """
        SELECT * FROM orders 
        WHERE bot_id = %s 
        AND created_at >= NOW() - INTERVAL 1 DAY
        ORDER BY created_at DESC
        LIMIT 20
    """
    db_orders = db.execute_query(query, (bot['id'],))
    
    print(f"\n📦 Ордеров в БД за 24ч: {len(db_orders)}")
    
    for order in db_orders:
        print(f"\n  Ордер {order['exchange_order_id']}:")
        print(f"    Символ: {order['symbol']}")
        print(f"    Статус в БД: {order['status']}")
        
        # Проверяем статус на бирже
        exchange_status = exchange.get_order_status(order['symbol'], order['exchange_order_id'])
        
        if exchange_status:
            print(f"    Статус на бирже: {exchange_status.get('status', 'unknown')}")
            
            # Сравниваем статусы
            if order['status'] != exchange_status.get('status', '').lower():
                print(f"    ⚠️  Статусы не совпадают!")
        else:
            print(f"    ❌ Ордер не найден на бирже")


if __name__ == "__main__":
    test_orders_sync()