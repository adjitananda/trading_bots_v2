#!/usr/bin/env python3
"""
Тест синхронизации между биржей и БД.
Проверяет:
1. Баланс (биржи vs рассчитанный в БД)
2. Открытые позиции (биржи vs БД)
3. Закрытые сделки (биржи vs БД)
4. PnL (биржи vs рассчитанный в БД)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from tabulate import tabulate

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.trading.exchange_client import ExchangeFactory
from src.trading.position_tracker import PositionTracker
from src.utils.time_utils import now_utc, utc_to_local


class SyncTester:
    """Тестер синхронизации биржи и БД"""
    
    def __init__(self, bot_name: str = None):
        self.bot_name = bot_name or 'TEST_BOT'
        self.bot = db.get_bot_by_name(self.bot_name)
        
        if not self.bot:
            print(f"❌ Бот {self.bot_name} не найден")
            print("Доступные боты:")
            bots = db.get_all_active_bots()
            for b in bots:
                print(f"  • {b['name']} (ID: {b['id']})")
            sys.exit(1)
        
        self.bot_id = self.bot['id']
        self.exchange = ExchangeFactory.create_client_for_bot(self.bot_name)
        self.tracker = PositionTracker(self.exchange, self.bot_id, self.bot_name)
        
        print(f"\n🔍 Тест синхронизации для бота: {self.bot_name} (ID: {self.bot_id})")
        print(f"📊 Биржа: {self.bot['exchange_name']}")
        print("=" * 70)
    
    def test_balance(self):
        """Тест 1: Проверка баланса"""
        print("\n📊 ТЕСТ 1: БАЛАНС")
        print("-" * 50)
        
        # Баланс с биржи
        exchange_balance = self.exchange.get_balance()
        
        # Баланс из последнего снимка в БД
        last_snapshot = db.get_last_snapshot(self.bot_id)
        db_balance = float(last_snapshot['balance']) if last_snapshot else 0.0
        
        # Рассчитываем баланс из сделок
        query = """
            SELECT 
                COALESCE(SUM(CASE WHEN side = 'BUY' THEN -entry_price * quantity ELSE 0 END), 0) as buy_cost,
                COALESCE(SUM(CASE WHEN side = 'SELL' THEN entry_price * quantity ELSE 0 END), 0) as sell_revenue,
                COALESCE(SUM(pnl), 0) as total_pnl
            FROM trades
            WHERE bot_id = %s AND status = 'closed'
        """
        trades_summary = db.execute_query(query, (self.bot_id,), fetch_one=True)
        
        # Начальный баланс (можно задать в конфиге)
        # Берем начальный баланс из первого снимка или используем текущий
        first_snapshot = db.execute_query(
            "SELECT balance FROM snapshots WHERE bot_id = %s ORDER BY timestamp ASC LIMIT 1",
            (self.bot_id,), fetch_one=True
        )
        initial_balance = float(first_snapshot['balance']) if first_snapshot else exchange_balance or 0
        
        calculated_balance = float(initial_balance) + float(trades_summary['total_pnl'] if trades_summary['total_pnl'] is not None else 0)
        
        print(f"💱 Баланс с биржи:         {exchange_balance:>10.2f} USDT")
        print(f"💾 Баланс из БД (снимок):  {db_balance:>10.2f} USDT")
        print(f"🧮 Рассчитанный баланс:    {calculated_balance:>10.2f} USDT")
        
        # Проверка расхождений
        if exchange_balance:
            diff_exchange_db = exchange_balance - float(db_balance)
            diff_exchange_calc = exchange_balance - float(calculated_balance)
            
            if abs(float(diff_exchange_db)) > 1.0:  # Допуск 1 USDT
                print(f"⚠️  Расхождение биржа vs БД: {diff_exchange_db:+.2f} USDT")
            else:
                print(f"✅ Биржа и БД совпадают (расхождение: {diff_exchange_db:+.2f})")
            
            if abs(float(diff_exchange_calc)) > 1.0:
                print(f"⚠️  Расхождение биржа vs расчет: {diff_exchange_calc:+.2f} USDT")
            else:
                print(f"✅ Биржа и расчет совпадают (расхождение: {diff_exchange_calc:+.2f})")
    
    def test_open_positions(self):
        """Тест 2: Проверка открытых позиций"""
        print("\n📊 ТЕСТ 2: ОТКРЫТЫЕ ПОЗИЦИИ")
        print("-" * 50)
        
        # Позиции с биржи
        exchange_positions = self.exchange.get_positions()
        exchange_positions = [p for p in exchange_positions if p['size'] > 0]
        
        # Позиции из БД
        db_positions = db.get_open_trades(self.bot_id)
        
        print(f"🔄 Позиций на бирже: {len(exchange_positions)}")
        print(f"💾 Позиций в БД:     {len(db_positions)}")
        
        # Детальное сравнение
        if exchange_positions:
            print("\n📈 Позиции на бирже:")
            for p in exchange_positions:
                print(f"  • {p['symbol']} {p['side']}: {p['size']} @ {p['entry_price']} (PnL: {p.get('unrealised_pnl', 0):+.2f})")
        
        if db_positions:
            print("\n📈 Позиции в БД:")
            for p in db_positions:
                print(f"  • {p['symbol']} {p['side']}: {p['quantity']} @ {p['entry_price']}")
        
        # Проверка соответствия
        exchange_symbols = {p['symbol'] for p in exchange_positions}
        db_symbols = {p['symbol'] for p in db_positions}
        
        only_in_exchange = exchange_symbols - db_symbols
        only_in_db = db_symbols - exchange_symbols
        
        if only_in_exchange:
            print(f"\n⚠️  Позиции только на бирже: {', '.join(only_in_exchange)}")
        if only_in_db:
            print(f"\n⚠️  Позиции только в БД: {', '.join(only_in_db)}")
        
        if not only_in_exchange and not only_in_db:
            print("\n✅ Все позиции синхронизированы")
    
    def test_closed_trades(self):
        """Тест 3: Проверка закрытых сделок"""
        print("\n📊 ТЕСТ 3: ЗАКРЫТЫЕ СДЕЛКИ")
        print("-" * 50)
        
        # Последние закрытые сделки с биржи
        exchange_trades = self.exchange.get_closed_pnl(limit=20)
        
        # Последние закрытые сделки из БД
        query = """
            SELECT * FROM trades 
            WHERE bot_id = %s AND status = 'closed'
            ORDER BY exit_time DESC
            LIMIT 20
        """
        db_trades = db.execute_query(query, (self.bot_id,))
        
        print(f"🔄 Сделок на бирже (последние 20): {len(exchange_trades)}")
        print(f"💾 Сделок в БД (последние 20):     {len(db_trades)}")
        
        if exchange_trades and db_trades:
            # Сравним суммарный PnL
            exchange_pnl = sum(t['pnl'] for t in exchange_trades)
            db_pnl = sum(t['pnl'] for t in db_trades if t['pnl'])
            
            print(f"\n💰 Суммарный PnL (биржа): {exchange_pnl:+.2f}")
            print(f"💰 Суммарный PnL (БД):    {db_pnl:+.2f}")
            
            # Проверим последние 5 сделок детально
            print("\n📋 Последние 5 сделок (биржа vs БД):")
            for i in range(min(5, len(exchange_trades), len(db_trades))):
                et = exchange_trades[i]
                dt = db_trades[i]
                print(f"\n  Сделка {i+1}:")
                print(f"    Символ:   {et['symbol']:10} vs {dt['symbol']:10}")
                print(f"    PnL:      {et['pnl']:>+8.2f} vs {dt['pnl']:>+8.2f}")
                print(f"    Время:    {datetime.fromtimestamp(int(et['created_time'])/1000).strftime('%H:%M')} vs {dt['exit_time'].strftime('%H:%M')}")
    
    def test_pnl_calculation(self):
        """Тест 4: Проверка расчета PnL"""
        print("\n📊 ТЕСТ 4: PnL КАЛЬКУЛЯЦИЯ")
        print("-" * 50)
        
        # PnL с биржи
        exchange_positions = self.exchange.get_positions()
        exchange_unrealized = sum(float(p.get('unrealised_pnl', 0)) for p in exchange_positions)
        
        # PnL из PositionTracker
        tracker_total = self.tracker.get_total_pnl()
        tracker_symbol = self.tracker.get_symbol_pnl()
        
        # PnL из БД
        summary = db.get_bot_summary(self.bot_id)
        db_realized = summary.get('total_pnl', 0)
        
        print(f"💱 Нереализованный PnL (биржа):  {exchange_unrealized:>+10.2f}")
        print(f"📊 Общий PnL (PositionTracker):  {tracker_total:>+10.2f}")
        print(f"📊 PnL по символу (Tracker):     {tracker_symbol:>+10.2f}")
        print(f"💾 Реализованный PnL (БД):       {db_realized:>+10.2f}")
        
        # Проверка формулы: tracker_total = db_realized + exchange_unrealized
        calculated_total = float(db_realized) + exchange_unrealized
        print(f"\n🧮 Проверка: БД + биржа = {calculated_total:+.2f}")
        print(f"   Tracker:              {tracker_total:+.2f}")
        
        if abs(calculated_total - tracker_total) < 0.01:
            print("✅ Формула расчета PnL корректна")
        else:
            print("⚠️  Расхождение в расчете PnL")
    
    def test_snapshots_consistency(self):
        """Тест 5: Проверка согласованности снимков"""
        print("\n📊 ТЕСТ 5: ИСТОРИЯ СНИМКОВ")
        print("-" * 50)
        
        query = """
            SELECT * FROM snapshots 
            WHERE bot_id = %s 
            ORDER BY timestamp DESC 
            LIMIT 10
        """
        snapshots = db.execute_query(query, (self.bot_id,))
        
        if not snapshots:
            print("❌ Нет снимков состояния")
            return
        
        print(f"📸 Последние {len(snapshots)} снимков:")
        
        for i, s in enumerate(snapshots):
            local_time = utc_to_local(s['timestamp'])
            print(f"\n  Снимок {i+1} [{local_time.strftime('%d.%m %H:%M')}]:")
            print(f"    Баланс: {s['balance']:>10.2f} | PnL: {s['total_pnl']:>+8.2f}")
            print(f"    Позиций: {s['open_positions_count']} | Просадка: {s['drawdown_current']:.2f}%")
            
            # Проверка изменения PnL между снимками
            if i < len(snapshots) - 1:
                prev = snapshots[i+1]
                pnl_change = s['total_pnl'] - prev['total_pnl']
                time_diff = (s['timestamp'] - prev['timestamp']).total_seconds() / 60
                print(f"    Изменение PnL: {pnl_change:>+8.2f} за {time_diff:.0f} мин")
    
    def run_all_tests(self):
        """Запустить все тесты"""
        print("\n" + "=" * 70)
        print("🚀 ЗАПУСК ПОЛНОЙ СИНХРОНИЗАЦИИ")
        print("=" * 70)
        
        self.test_balance()
        self.test_open_positions()
        self.test_closed_trades()
        self.test_pnl_calculation()
        self.test_snapshots_consistency()
        
        print("\n" + "=" * 70)
        print("✅ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 70)


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Тест синхронизации биржи и БД')
    parser.add_argument('--bot', type=str, default='TEST_BOT',
                       help='Имя бота для тестирования')
    parser.add_argument('--test', type=str,
                       choices=['balance', 'positions', 'trades', 'pnl', 'snapshots', 'all'],
                       default='all', help='Конкретный тест для запуска')
    
    args = parser.parse_args()
    
    tester = SyncTester(args.bot)
    
    if args.test == 'all':
        tester.run_all_tests()
    elif args.test == 'balance':
        tester.test_balance()
    elif args.test == 'positions':
        tester.test_open_positions()
    elif args.test == 'trades':
        tester.test_closed_trades()
    elif args.test == 'pnl':
        tester.test_pnl_calculation()
    elif args.test == 'snapshots':
        tester.test_snapshots_consistency()


if __name__ == "__main__":
    main()