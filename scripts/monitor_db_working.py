#!/usr/bin/env python3
"""
Рабочий мониторинг базы данных в реальном времени.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.utils.time_utils import utc_to_local


class DatabaseMonitor:
    def __init__(self, bot_name: str = None):
        self.bot_name = bot_name
        self.bot_id = None
        
        if bot_name:
            bot = db.get_bot_by_name(bot_name)
            if bot:
                self.bot_id = bot['id']
                print(f"📊 Мониторинг для бота: {bot_name} (ID: {self.bot_id})")
        
        self.last_ids = {
            'trades': 0,
            'orders': 0,
            'snapshots': 0,
            'alerts': 0
        }
        self.running = True
    
    def get_new_trades(self):
        """Получить новые сделки"""
        if self.bot_id:
            query = """
                SELECT 
                    t.id, b.name as bot_name, t.symbol, t.side,
                    t.status, t.entry_time, t.entry_price, t.quantity,
                    t.exit_time, t.exit_price, t.pnl, t.pnl_percent, t.exit_reason
                FROM trades t
                JOIN bots b ON t.bot_id = b.id
                WHERE t.id > %s AND t.bot_id = %s
                ORDER BY t.id
            """
            return db.execute_query(query, (self.last_ids['trades'], self.bot_id))
        return []
    
    def get_new_orders(self):
        """Получить новые ордера"""
        if self.bot_id:
            query = """
                SELECT 
                    o.id, o.exchange_order_id, b.name as bot_name,
                    o.symbol, o.side, o.order_type, o.quantity,
                    o.price, o.status, o.filled_quantity,
                    o.average_fill_price, o.created_at
                FROM orders o
                JOIN bots b ON o.bot_id = b.id
                WHERE o.id > %s AND o.bot_id = %s
                ORDER BY o.id
            """
            return db.execute_query(query, (self.last_ids['orders'], self.bot_id))
        return []
    
    def get_new_snapshots(self):
        """Получить новые снимки"""
        if self.bot_id:
            query = """
                SELECT 
                    s.id, b.name as bot_name, s.timestamp,
                    s.balance, s.total_pnl, s.daily_pnl,
                    s.open_positions_count, s.drawdown_current, s.drawdown_max
                FROM snapshots s
                JOIN bots b ON s.bot_id = b.id
                WHERE s.id > %s AND s.bot_id = %s
                ORDER BY s.id
            """
            return db.execute_query(query, (self.last_ids['snapshots'], self.bot_id))
        return []
    
    def print_trades(self, trades):
        """Вывести новые сделки"""
        for t in trades:
            local_time = utc_to_local(t['entry_time'])
            status = "🟢" if t['status'] == 'open' else "🔴"
            
            print(f"\n{status} СДЕЛКА {t['id']} | {t['bot_name']} | {t['symbol']} | {t['side']}")
            print(f"   Вход: {local_time.strftime('%H:%M:%S')} @ {float(t['entry_price']):.4f}")
            print(f"   Количество: {float(t['quantity']):.4f}")
            
            if t['status'] == 'closed' and t['exit_time']:
                local_exit = utc_to_local(t['exit_time'])
                print(f"   Выход: {local_exit.strftime('%H:%M:%S')} @ {float(t['exit_price']):.4f}")
                print(f"   PnL: {float(t['pnl']):+.2f} USDT ({float(t['pnl_percent']):+.2f}%)")
            
            self.last_ids['trades'] = max(self.last_ids['trades'], t['id'])
    
    def print_orders(self, orders):
        """Вывести новые ордера"""
        for o in orders:
            local_time = utc_to_local(o['created_at'])
            status = "✅" if o['status'] == 'filled' else "⏳"
            
            print(f"\n{status} ОРДЕР {o['id']} | {o['bot_name']} | {o['symbol']} | {o['side']}")
            print(f"   ID на бирже: {o['exchange_order_id']}")
            print(f"   Тип: {o['order_type']}, Количество: {float(o['quantity']):.4f}")
            print(f"   Статус: {o['status']}, Время: {local_time.strftime('%H:%M:%S')}")
            
            if o['filled_quantity']:
                print(f"   Исполнено: {float(o['filled_quantity']):.4f} @ {float(o['average_fill_price']):.4f}")
            
            self.last_ids['orders'] = max(self.last_ids['orders'], o['id'])
    
    def print_snapshots(self, snapshots):
        """Вывести новые снимки"""
        for s in snapshots:
            local_time = utc_to_local(s['timestamp'])
            
            print(f"\n📸 СНИМОК {s['id']} | {s['bot_name']}")
            print(f"   Время: {local_time.strftime('%H:%M:%S')}")
            print(f"   Баланс: {float(s['balance']):.2f} USDT")
            print(f"   PnL: {float(s['total_pnl']):+.2f} USDT")
            print(f"   Позиций: {s['open_positions_count']}, Просадка: {float(s['drawdown_current']):.2f}%")
            
            self.last_ids['snapshots'] = max(self.last_ids['snapshots'], s['id'])
    
    def run(self, interval=2):
        print(f"\n{'='*60}")
        print(f"🚀 МОНИТОРИНГ БАЗЫ ДАННЫХ")
        print(f"📊 Бот: {self.bot_name or 'ВСЕ'}, Интервал: {interval}с")
        print(f"{'='*60}\n")
        
        try:
            while self.running:
                trades = self.get_new_trades()
                orders = self.get_new_orders()
                snapshots = self.get_new_snapshots()
                
                if trades or orders or snapshots:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Новые записи:")
                    self.print_trades(trades)
                    self.print_orders(orders)
                    self.print_snapshots(snapshots)
                    print("-" * 40)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n✅ Мониторинг остановлен")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bot', default='TEST_BOT', help='Имя бота')
    parser.add_argument('--interval', type=int, default=2, help='Интервал обновления (сек)')
    args = parser.parse_args()
    
    monitor = DatabaseMonitor(args.bot)
    monitor.run(args.interval)
