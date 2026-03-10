#!/usr/bin/env python3
"""
Мониторинг синхронизации в реальном времени
Запускается каждые N секунд и показывает изменения
"""

import sys
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.trading.exchange_client import ExchangeFactory


def monitor(bot_name='TEST_BOT', interval=10):
    """Мониторинг синхронизации"""
    
    bot = db.get_bot_by_name(bot_name)
    if not bot:
        print(f"❌ Бот {bot_name} не найден")
        return
    
    exchange = ExchangeFactory.create_client_for_bot(bot_name)
    
    print(f"\n📊 МОНИТОРИНГ СИНХРОНИЗАЦИИ (обновление каждые {interval}с)")
    print("=" * 70)
    
    last_positions = set()
    last_trades_count = 0
    
    try:
        while True:
            print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
            print("-" * 50)
            
            # Текущие позиции на бирже
            positions = exchange.get_positions()
            current_positions = {p['symbol'] for p in positions if p['size'] > 0}
            
            # Новые позиции
            new_positions = current_positions - last_positions
            if new_positions:
                print(f"🆕 Новые позиции: {', '.join(new_positions)}")
            
            # Закрытые позиции
            closed_positions = last_positions - current_positions
            if closed_positions:
                print(f"❌ Закрыты: {', '.join(closed_positions)}")
            
            # Количество сделок в БД
            query = "SELECT COUNT(*) as count FROM trades WHERE bot_id = %s"
            trades_count = db.execute_query(query, (bot['id'],), fetch_one=True)['count']
            
            if trades_count != last_trades_count:
                print(f"📈 Новых сделок в БД: {trades_count - last_trades_count}")
                last_trades_count = trades_count
            
            # Баланс
            balance = exchange.get_balance()
            if balance:
                print(f"💰 Баланс: {balance:.2f} USDT")
            
            last_positions = current_positions
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n✅ Мониторинг остановлен")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bot', default='TEST_BOT')
    parser.add_argument('--interval', type=int, default=10)
    args = parser.parse_args()
    
    monitor(args.bot, args.interval)