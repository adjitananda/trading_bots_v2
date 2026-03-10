#!/usr/bin/env python3
"""
Мониторинг биржи в реальном времени.
Показывает текущие позиции, баланс, цены и ордера.
"""

import sys
import time
import os
from pathlib import Path
from datetime import datetime
from tabulate import tabulate

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.trading.exchange_client import ExchangeFactory
from src.utils.time_utils import now_utc, utc_to_local


class ExchangeMonitor:
    """Мониторинг биржи в реальном времени"""
    
    def __init__(self, exchange_name='bybit', symbols=None):
        self.exchange = ExchangeFactory.create_client(exchange_name)
        self.exchange_name = exchange_name
        self.symbols = symbols or ['BTCUSDT', 'ETHUSDT', 'LTCUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT']
        self.running = True
        
        # Для отслеживания изменений
        self.last_positions = {}
        self.last_balance = None
    
    def get_market_prices(self):
        """Получить текущие цены"""
        prices = {}
        for symbol in self.symbols:
            try:
                price = self.exchange.get_current_price(symbol)
                if price:
                    prices[symbol] = price
            except:
                pass
            time.sleep(0.1)  # Чтобы не превысить rate limit
        return prices
    
    def print_header(self):
        """Вывести заголовок"""
        os.system('clear')  # Очищаем экран
        local_time = utc_to_local(now_utc())
        
        print(f"{'='*100}")
        print(f"📊 МОНИТОРИНГ БИРЖИ {self.exchange_name.upper()} | {local_time.strftime('%d.%m.%Y %H:%M:%S')}")
        print(f"{'='*100}")
    
    def print_balance(self, balance):
        """Вывести баланс"""
        if balance is not None:
            change = ""
            if self.last_balance is not None:
                diff = balance - self.last_balance
                if abs(diff) > 0.01:
                    change = f" ({diff:+.2f})"
            
            print(f"\n💰 БАЛАНС: {balance:.2f} USDT{change}")
            self.last_balance = balance
    
    def print_positions(self, positions):
        """Вывести позиции"""
        open_positions = [p for p in positions if p['size'] > 0]
        
        print(f"\n📈 ОТКРЫТЫЕ ПОЗИЦИИ ({len(open_positions)})")
        
        if open_positions:
            # Сортируем по символу
            open_positions.sort(key=lambda x: x['symbol'])
            
            # Создаем таблицу
            table = []
            for p in open_positions:
                # Отслеживаем изменения
                key = p['symbol']
                change_indicator = ""
                if key in self.last_positions:
                    old_pnl = self.last_positions[key].get('unrealised_pnl', 0)
                    new_pnl = p.get('unrealised_pnl', 0)
                    if abs(new_pnl - old_pnl) > 0.01:
                        change_indicator = f" ({new_pnl - old_pnl:+.2f})"
                
                table.append([
                    p['symbol'],
                    p['side'],
                    f"{p['size']:.4f}",
                    f"{p['entry_price']:.4f}",
                    f"{p.get('mark_price', 0):.4f}",
                    f"{p.get('unrealised_pnl', 0):+.2f}{change_indicator}",
                    f"{((p.get('mark_price', p['entry_price']) - p['entry_price']) / p['entry_price'] * 100):+.2f}%"
                ])
                
                # Сохраняем для следующего раза
                self.last_positions[key] = p
            
            headers = ['Symbol', 'Side', 'Size', 'Entry', 'Mark', 'PnL', 'PnL%']
            print(tabulate(table, headers=headers, tablefmt='grid'))
            
            # Итого PnL
            total_pnl = sum(p.get('unrealised_pnl', 0) for p in open_positions)
            print(f"\n💹 Нереализованный PnL: {total_pnl:+.2f} USDT")
        else:
            print("  Нет открытых позиций")
    
    def print_market_prices(self, prices):
        """Вывести рыночные цены"""
        print(f"\n📊 РЫНОЧНЫЕ ЦЕНЫ")
        
        if prices:
            table = []
            for symbol, price in prices.items():
                table.append([symbol, f"{price:.4f}"])
            
            headers = ['Symbol', 'Price']
            print(tabulate(table, headers=headers, tablefmt='grid'))
    
    def print_recent_trades(self):
        """Вывести последние сделки с биржи"""
        try:
            trades = self.exchange.get_closed_pnl(limit=5)
            if trades:
                print(f"\n📋 ПОСЛЕДНИЕ СДЕЛКИ (с биржи)")
                
                table = []
                for t in trades[:5]:
                    table.append([
                        t['symbol'],
                        t['side'],
                        f"{t['quantity']:.4f}",
                        f"{t['pnl']:+.2f}",
                        datetime.fromtimestamp(int(t['created_time'])/1000).strftime('%H:%M:%S')
                    ])
                
                headers = ['Symbol', 'Side', 'Qty', 'PnL', 'Time']
                print(tabulate(table, headers=headers, tablefmt='grid'))
        except:
            pass
    
    def run(self, interval=3):
        """Запустить мониторинг"""
        print(f"\n{'='*100}")
        print(f"🚀 МОНИТОРИНГ БИРЖИ ЗАПУЩЕН")
        print(f"📊 Интервал обновления: {interval} сек")
        print(f"{'='*100}")
        print("\nНажмите Ctrl+C для выхода")
        
        time.sleep(2)
        
        try:
            while self.running:
                # Получаем данные
                balance = self.exchange.get_balance()
                positions = self.exchange.get_positions()
                prices = self.get_market_prices()
                
                # Выводим
                self.print_header()
                self.print_balance(balance)
                self.print_positions(positions)
                self.print_market_prices(prices)
                self.print_recent_trades()
                
                # Ждем
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n✅ Мониторинг остановлен")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Мониторинг биржи')
    parser.add_argument('--exchange', default='bybit', help='Имя биржи')
    parser.add_argument('--interval', type=int, default=3, help='Интервал обновления (сек)')
    parser.add_argument('--symbols', nargs='+', help='Список символов для отслеживания')
    
    args = parser.parse_args()
    
    monitor = ExchangeMonitor(args.exchange, args.symbols)
    monitor.run(args.interval)


if __name__ == "__main__":
    main()