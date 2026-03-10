#!/usr/bin/env python3
"""
Ручное управление сделками для тестирования.
Позволяет открывать и закрывать позиции по команде.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import time

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.trading.exchange_client import ExchangeFactory, ExchangeError
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.utils.time_utils import now_utc, utc_to_local
from src.messages.console_messages import ConsoleMessages


class ManualTrader:
    """Ручной трейдер для тестирования"""
    
    def __init__(self, bot_name='TEST_BOT'):
        self.bot_name = bot_name
        self.bot = db.get_bot_by_name(bot_name)
        
        if not self.bot:
            print(f"❌ Бот {bot_name} не найден")
            print("Доступные боты:")
            for b in db.get_all_active_bots():
                print(f"  • {b['name']}")
            sys.exit(1)
        
        self.bot_id = self.bot['id']
        self.exchange = ExchangeFactory.create_client_for_bot(bot_name)
        self.order_manager = OrderManager(self.exchange, self.bot_id, bot_name)
        self.tracker = PositionTracker(self.exchange, self.bot_id, bot_name)
        
        print(f"\n🤖 Ручной трейдер для бота: {bot_name} (ID: {self.bot_id})")
        print(f"📊 Биржа: {self.bot['exchange_name']}")
        print("=" * 60)
    
    def show_status(self):
        """Показать текущий статус"""
        balance = self.exchange.get_balance()
        positions = self.tracker.get_positions_summary()
        realized_pnl = db.get_bot_summary(self.bot_id).get('total_pnl', 0)
        
        print(f"\n📊 ТЕКУЩИЙ СТАТУС")
        print("-" * 40)
        print(f"💰 Баланс: {balance:.2f} USDT")
        print(f"📈 Открытых позиций: {positions['total_positions']}")
        print(f"💸 Реализованный PnL: {float(realized_pnl):+.2f} USDT")
        print(f"💹 Нереализованный PnL: {positions['total_pnl']:.2f} USDT")
        print(f"💵 Общий PnL: {float(realized_pnl) + positions['total_pnl']:.2f} USDT")
        
        if positions['positions']:
            print(f"\n📋 Открытые позиции:")
            for p in positions['positions']:
                print(f"  • {p['symbol']} {p['side']}: {p['size']} @ {p['entry_price']} (PnL: {p['pnl']:+.2f})")
    
    def buy(self, symbol: str, usdt_amount: float = 10, tp_percent: float = 2.0, sl_percent: float = 1.0):
        """Открыть LONG позицию"""
        print(f"\n🟢 ПОКУПКА {symbol}")
        print("-" * 40)
        
        # Получаем текущую цену
        price = self.exchange.get_current_price(symbol)
        if not price:
            print(f"❌ Не удалось получить цену для {symbol}")
            return
        
        print(f"💰 Текущая цена: {price:.4f} USDT")
        
        # Рассчитываем количество
        quantity = self.exchange.calculate_quantity(symbol, usdt_amount, price)
        print(f"🔢 Количество: {quantity:.4f} ({usdt_amount} USDT)")
        
        # Рассчитываем TP и SL
        tp_price = price * (1 + tp_percent / 100)
        sl_price = price * (1 - sl_percent / 100)
        print(f"🎯 Take Profit: {tp_price:.4f} (+{tp_percent}%)")
        print(f"🛑 Stop Loss: {sl_price:.4f} (-{sl_percent}%)")
        
        # Подтверждение
        response = input("\n❓ Подтвердите открытие позиции (y/n): ")
        if response.lower() != 'y':
            print("❌ Отменено")
            return
        
        # Открываем позицию
        result = self.order_manager.place_market_order(
            symbol=symbol,
            side='buy',
            quantity=quantity,
            take_profit=tp_price,
            stop_loss=sl_price,
            tp_percent=tp_percent,
            sl_percent=sl_percent
        )
        
        if result['success']:
            print(f"\n✅ ПОЗИЦИЯ ОТКРЫТА")
            print(f"  Order ID: {result['order_id']}")
            print(f"  Trade ID: {result['trade_id']}")
            print(f"  Цена входа: {result['entry_price']:.4f}")
            
            # Покажем обновленный статус
            self.show_status()
        else:
            print(f"\n❌ Ошибка: {result.get('error', 'Unknown error')}")
    
    def sell(self, symbol: str, usdt_amount: float = 10, tp_percent: float = 2.0, sl_percent: float = 1.0):
        """Открыть SHORT позицию"""
        print(f"\n🔴 ПРОДАЖА {symbol}")
        print("-" * 40)
        
        # Получаем текущую цену
        price = self.exchange.get_current_price(symbol)
        if not price:
            print(f"❌ Не удалось получить цену для {symbol}")
            return
        
        print(f"💰 Текущая цена: {price:.4f} USDT")
        
        # Рассчитываем количество
        quantity = self.exchange.calculate_quantity(symbol, usdt_amount, price)
        print(f"🔢 Количество: {quantity:.4f} ({usdt_amount} USDT)")
        
        # Для SHORT TP ниже цены, SL выше цены
        tp_price = price * (1 - tp_percent / 100)
        sl_price = price * (1 + sl_percent / 100)
        print(f"🎯 Take Profit: {tp_price:.4f} (+{tp_percent}%)")
        print(f"🛑 Stop Loss: {sl_price:.4f} (-{sl_percent}%)")
        
        # Подтверждение
        response = input("\n❓ Подтвердите открытие позиции (y/n): ")
        if response.lower() != 'y':
            print("❌ Отменено")
            return
        
        # Открываем позицию
        result = self.order_manager.place_market_order(
            symbol=symbol,
            side='sell',
            quantity=quantity,
            take_profit=tp_price,
            stop_loss=sl_price,
            tp_percent=tp_percent,
            sl_percent=sl_percent
        )
        
        if result['success']:
            print(f"\n✅ ПОЗИЦИЯ ОТКРЫТА")
            print(f"  Order ID: {result['order_id']}")
            print(f"  Trade ID: {result['trade_id']}")
            print(f"  Цена входа: {result['entry_price']:.4f}")
            
            # Покажем обновленный статус
            self.show_status()
        else:
            print(f"\n❌ Ошибка: {result.get('error', 'Unknown error')}")
    
    def close(self, symbol: str = None):
        """Закрыть позицию (по символу или все)"""
        print(f"\n❌ ЗАКРЫТИЕ ПОЗИЦИЙ")
        print("-" * 40)
        
        positions = self.exchange.get_positions()
        open_positions = [p for p in positions if p['size'] > 0]
        
        if not open_positions:
            print("📭 Нет открытых позиций")
            return
        
        # Фильтруем по символу если указан
        if symbol:
            positions_to_close = [p for p in open_positions if p['symbol'] == symbol]
            if not positions_to_close:
                print(f"❌ Нет открытой позиции по {symbol}")
                return
        else:
            positions_to_close = open_positions
        
        print(f"\n📋 Позиции к закрытию:")
        for p in positions_to_close:
            print(f"  • {p['symbol']} {p['side']}: {p['size']} @ {p['entry_price']} (PnL: {p.get('unrealised_pnl', 0):+.2f})")
        
        response = input(f"\n❓ Закрыть {len(positions_to_close)} позиций? (y/n): ")
        if response.lower() != 'y':
            print("❌ Отменено")
            return
        
        # Закрываем каждую позицию
        for pos in positions_to_close:
            try:
                # Для закрытия используем рыночный ордер противоположной стороны
                close_side = 'sell' if pos['side'] == 'LONG' else 'buy'
                
                result = self.order_manager.place_market_order(
                    symbol=pos['symbol'],
                    side=close_side,
                    quantity=pos['size']
                )
                
                if result['success']:
                    print(f"  ✅ {pos['symbol']} закрыта")
                else:
                    print(f"  ❌ {pos['symbol']}: {result.get('error', 'Unknown error')}")
                
                time.sleep(0.5)  # Небольшая пауза между ордерами
                
            except Exception as e:
                print(f"  ❌ {pos['symbol']}: {e}")
        
        # Проверим закрытые сделки
        print("\n🔄 Проверка закрытых сделок...")
        closed = self.order_manager.check_closed_positions()
        print(f"  Найдено закрытых сделок: {len(closed)}")
        
        # Покажем обновленный статус
        self.show_status()
    
    def monitor(self, interval: int = 5):
        """Мониторинг позиций в реальном времени"""
        print(f"\n📊 МОНИТОРИНГ (обновление каждые {interval}с)")
        print("=" * 60)
        print("Нажмите Ctrl+C для выхода")
        print("=" * 60)
        
        try:
            while True:
                # Получаем текущие данные
                balance = self.exchange.get_balance()
                positions = self.tracker.get_positions_summary()
                
                # Очищаем экран (для Linux)
                print("\033c", end="")
                
                # Показываем время
                local_time = utc_to_local(now_utc())
                print(f"⏰ {local_time.strftime('%d.%m.%Y %H:%M:%S')}")
                print("-" * 60)
                
                # Баланс и PnL
                print(f"💰 Баланс: {balance:.2f} USDT")
                print(f"📈 Открытых позиций: {positions['total_positions']}")
                print(f"💹 Нереализованный PnL: {positions['total_pnl']:+.2f} USDT")
                print("-" * 60)
                
                # Позиции
                if positions['positions']:
                    for p in positions['positions']:
                        print(f"{p['symbol']}: {p['side']} {p['size']} @ {p['entry_price']} | "
                              f"PnL: {p['pnl']:+.2f} ({p['pnl_percent']:+.2f}%)")
                else:
                    print("📭 Нет открытых позиций")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n✅ Мониторинг остановлен")


def main():
    parser = argparse.ArgumentParser(description='Ручной трейдер для тестирования')
    parser.add_argument('--bot', default='TEST_BOT', help='Имя бота')
    
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Команда status
    subparsers.add_parser('status', help='Показать статус')
    
    # Команда monitor
    monitor_parser = subparsers.add_parser('monitor', help='Мониторинг в реальном времени')
    monitor_parser.add_argument('--interval', type=int, default=5, help='Интервал обновления (сек)')
    
    # Команда buy
    buy_parser = subparsers.add_parser('buy', help='Купить (LONG)')
    buy_parser.add_argument('symbol', help='Символ (например LTCUSDT)')
    buy_parser.add_argument('--amount', type=float, default=10, help='Сумма в USDT')
    buy_parser.add_argument('--tp', type=float, default=2.0, help='Take Profit %')
    buy_parser.add_argument('--sl', type=float, default=1.0, help='Stop Loss %')
    
    # Команда sell
    sell_parser = subparsers.add_parser('sell', help='Продать (SHORT)')
    sell_parser.add_argument('symbol', help='Символ (например LTCUSDT)')
    sell_parser.add_argument('--amount', type=float, default=10, help='Сумма в USDT')
    sell_parser.add_argument('--tp', type=float, default=2.0, help='Take Profit %')
    sell_parser.add_argument('--sl', type=float, default=1.0, help='Stop Loss %')
    
    # Команда close
    close_parser = subparsers.add_parser('close', help='Закрыть позицию(и)')
    close_parser.add_argument('--symbol', help='Символ (если не указан, закрыть все)')
    
    args = parser.parse_args()
    
    trader = ManualTrader(args.bot)
    
    if args.command == 'status':
        trader.show_status()
    elif args.command == 'monitor':
        trader.monitor(args.interval)
    elif args.command == 'buy':
        trader.buy(args.symbol, args.amount, args.tp, args.sl)
    elif args.command == 'sell':
        trader.sell(args.symbol, args.amount, args.tp, args.sl)
    elif args.command == 'close':
        trader.close(args.symbol)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


# 4. Как использовать:
# bash
# # Активируем окружение
# cd /home/trader/trading_bots_v2
# source /home/trader/.venv/bin/activate

# # Посмотреть статус
# python scripts/manual_trade.py status

# # Купить LTCUSDT (LONG) на 10 USDT с TP=2%, SL=1%
# python scripts/manual_trade.py buy LTCUSDT --amount 10 --tp 2 --sl 1

# # Продать LTCUSDT (SHORT)
# python scripts/manual_trade.py sell LTCUSDT --amount 10 --tp 2 --sl 1

# # Закрыть все позиции
# python scripts/manual_trade.py close

# # Закрыть только LTCUSDT
# python scripts/manual_trade.py close --symbol LTCUSDT

# # Мониторинг в реальном времени (обновление каждые 3 сек)
# python scripts/manual_trade.py monitor --interval 3

# # Запустить тестовый скрипт
# ./scripts/test_ltc.sh