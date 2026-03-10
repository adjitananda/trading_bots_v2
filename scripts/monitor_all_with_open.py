#!/usr/bin/env python3
"""
Мониторинг всех ботов с отображением открытых сделок
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.utils.time_utils import utc_to_local


class FullMonitor:
    def __init__(self):
        self.last_snapshot_id = 0
        self.last_trade_id = 0
        self.last_order_id = 0
        self.running = True
        
        # Получаем всех ботов
        self.bots = {bot['id']: bot['name'] for bot in db.get_all_active_bots()}
        print(f"\n{'='*60}")
        print(f"🚀 ПОЛНЫЙ МОНИТОРИНГ БОТОВ")
        print(f"{'='*60}")
        print(f"\n📊 Активных ботов: {len(self.bots)}")
        for bot_id, bot_name in self.bots.items():
            print(f"   • {bot_name} (ID: {bot_id})")
        
        # Показываем текущие открытые позиции
        self.show_open_positions()
        print(f"{'='*60}\n")
    
    def show_open_positions(self):
        """Показать текущие открытые позиции"""
        open_trades = db.get_open_trades()
        if open_trades:
            print(f"\n🔓 ТЕКУЩИЕ ОТКРЫТЫЕ ПОЗИЦИИ:")
            for t in open_trades:
                entry_time = utc_to_local(t['entry_time'])
                minutes_open = (datetime.now() - entry_time.replace(tzinfo=None)).total_seconds() / 60
                print(f"   • {t['bot_name']}: {t['symbol']} {t['side']} @ {float(t['entry_price']):.4f} "
                      f"({minutes_open:.0f} мин)")
    
    def get_new_data(self):
        """Получить новые данные"""
        # Новые снапшоты
        snapshots = db.execute_query(
            "SELECT s.*, b.name as bot_name FROM snapshots s "
            "JOIN bots b ON s.bot_id = b.id "
            "WHERE s.id > %s ORDER BY s.id",
            (self.last_snapshot_id,)
        )
        
        # Новые сделки (включая открытые)
        trades = db.execute_query(
            "SELECT t.*, b.name as bot_name FROM trades t "
            "JOIN bots b ON t.bot_id = b.id "
            "WHERE t.id > %s ORDER BY t.id",
            (self.last_trade_id,)
        )
        
        # Новые ордера
        orders = db.execute_query(
            "SELECT o.*, b.name as bot_name FROM orders o "
            "JOIN bots b ON o.bot_id = b.id "
            "WHERE o.id > %s ORDER BY o.id",
            (self.last_order_id,)
        )
        
        return snapshots, trades, orders
    
    def print_snapshots(self, snapshots):
        for s in snapshots:
            local_time = utc_to_local(s['timestamp'])
            print(f"\n📸 СНИМОК {s['id']} | {s['bot_name']}")
            print(f"   Время: {local_time.strftime('%H:%M:%S')}")
            print(f"   Баланс: {float(s['balance']):.2f} USDT")
            print(f"   PnL: {float(s['total_pnl']):+.2f} USDT")
            print(f"   Позиций: {s['open_positions_count']}")
            self.last_snapshot_id = max(self.last_snapshot_id, s['id'])
    
    def print_trades(self, trades):
        for t in trades:
            local_time = utc_to_local(t['entry_time'])
            status = "🟢" if t['status'] == 'open' else "🔴"
            
            print(f"\n{status} СДЕЛКА {t['id']} | {t['bot_name']} | {t['symbol']} | {t['side']}")
            print(f"   Статус: {t['status']}")
            print(f"   Вход: {local_time.strftime('%H:%M:%S')} @ {float(t['entry_price']):.4f}")
            print(f"   Количество: {float(t['quantity']):.4f}")
            
            if t['status'] == 'closed' and t['exit_time']:
                local_exit = utc_to_local(t['exit_time'])
                print(f"   Выход: {local_exit.strftime('%H:%M:%S')} @ {float(t['exit_price']):.4f}")
                print(f"   PnL: {float(t['pnl']):+.2f} USDT ({float(t['pnl_percent']):+.2f}%)")
            
            self.last_trade_id = max(self.last_trade_id, t['id'])
    
    def print_orders(self, orders):
        for o in orders:
            local_time = utc_to_local(o['created_at'])
            status = "✅" if o['status'] == 'filled' else "⏳"
            
            print(f"\n{status} ОРДЕР {o['id']} | {o['bot_name']} | {o['symbol']} | {o['side']}")
            print(f"   Статус: {o['status']}, Время: {local_time.strftime('%H:%M:%S')}")
            self.last_order_id = max(self.last_order_id, o['id'])
    
    def run(self, interval=2):
        try:
            while self.running:
                snapshots, trades, orders = self.get_new_data()
                
                if snapshots or trades or orders:
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
    parser.add_argument('--interval', type=int, default=2, help='Интервал обновления (сек)')
    args = parser.parse_args()
    
    monitor = FullMonitor()
    monitor.run(args.interval)
