#!/usr/bin/env python3
"""
Тестовый скрипт для проверки получения закрытых позиций с биржи
и отправки уведомлений.
Запускается вручную, опрашивает биржу каждые 10 секунд.
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from pprint import pprint

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.trading.exchange_client import ExchangeFactory
from src.core.database import db
from src.telegram.notifier import notifier

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClosedPositionsTester:
    """Простой тестер закрытых позиций"""
    
    def __init__(self, symbol: str = "ETHUSDT"):
        self.symbol = symbol
        self.exchange = ExchangeFactory.create_client("bybit")
        self.bot = db.get_bot_by_name(symbol)
        
        print("\n" + "="*70)
        print("🔍 ТЕСТЕР ЗАКРЫТЫХ ПОЗИЦИЙ")
        print("="*70)
        print(f"📊 Символ: {symbol}")
        print(f"🤖 Бот ID: {self.bot['id'] if self.bot else 'Не найден'}")
        print(f"📡 Биржа: bybit")
        print("="*70)
        
        # Для отслеживания уже обработанных ордеров
        self.processed_orders = set()
    
    def get_closed_positions_from_exchange(self):
        """Получить закрытые позиции напрямую с биржи"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 Запрос к бирже...")
        
        try:
            # Попробуем разные варианты запросов
            print("  Вариант 1: get_closed_pnl с category='linear'")
            closed1 = self.exchange.get_closed_pnl(symbol=self.symbol if self.symbol != "ALL" else None, limit=50)
            print(f"    Результат: {len(closed1)} записей")
            
            # Если есть возможность, попробуем другие методы
            # Например, получить открытые позиции для проверки соединения
            print("\n  Вариант 2: Проверка соединения (get_positions)")
            positions = self.exchange.get_positions()
            print(f"    Открытых позиций: {len(positions)}")
            
            # Покажем первые несколько позиций если есть
            if positions:
                print(f"    Первая позиция: {positions[0]}")
            
            return closed1
            
        except Exception as e:
            print(f"❌ Ошибка при запросе к бирже: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def check_database_for_trade(self, order_id: str):
        """Проверить, есть ли сделка в БД по order_id"""
        if not order_id:
            return None
        
        # Ищем в trades по entry_order_id или exit_order_id
        trades = db.get_trades_by_order_id(order_id)
        
        if trades:
            trade = trades[0]
            print(f"  📊 Найдена сделка в БД: ID={trade['id']}, статус={trade['status']}")
            return trade
        else:
            print(f"  📊 Сделка с order_id {order_id} в БД НЕ НАЙДЕНА")
            
            # Поищем в orders
            orders = db.get_orders_by_exchange_id(order_id)
            if orders:
                print(f"  📊 Найден ордер в БД: ID={orders[0]['id']}, статус={orders[0]['status']}")
                print(f"  📊 Связан с trade_id={orders[0].get('trade_id')}")
            
            return None
    
    def check_all_filters(self, closed_item):
        """Проверить все фильтры, которые применяет OrderManager"""
        print("\n  🔍 ПРОВЕРКА ФИЛЬТРОВ:")
        
        order_id = closed_item.get("order_id")
        if not order_id:
            print("  ❌ Фильтр 0: Нет order_id")
            return False
        
        # Фильтр 1: Проверка возраста
        created_time = closed_item.get("created_time")
        if created_time:
            try:
                order_time = datetime.fromtimestamp(int(created_time) / 1000)
                age_hours = (datetime.now() - order_time).total_seconds() / 3600
                print(f"  ⏱️ Фильтр 1: Возраст ордера = {age_hours:.1f} часов")
                if age_hours > 24:
                    print(f"  ❌ Ордер старше 24 часов ({age_hours:.1f} > 24)")
                else:
                    print(f"  ✅ Ордер младше 24 часов")
            except Exception as e:
                print(f"  ⚠️ Ошибка при расчете возраста: {e}")
        
        # Фильтр 2: Проверка, есть ли ордер в БД
        existing_orders = db.get_orders_by_exchange_id(order_id)
        if existing_orders:
            order_in_db = existing_orders[0]
            print(f"  📦 Фильтр 2: Ордер найден в БД, статус={order_in_db['status']}")
            if order_in_db["status"] in ["filled", "cancelled", "rejected"]:
                print(f"  ❌ Ордер уже в финальном статусе")
            else:
                print(f"  ✅ Ордер ещё не в финальном статусе")
        else:
            print(f"  📦 Фильтр 2: Ордера в БД нет")
        
        # Фильтр 3: Проверка, есть ли сделка в БД
        existing_trades = db.get_trades_by_order_id(order_id)
        if existing_trades:
            trade = existing_trades[0]
            print(f"  💼 Фильтр 3: Сделка найдена в БД, статус={trade['status']}")
            if trade["status"] == "closed":
                print(f"  ❌ Сделка уже закрыта")
            else:
                print(f"  ✅ Сделка ещё открыта")
        else:
            print(f"  💼 Фильтр 3: Сделки в БД нет")
        
        # Все проверки пройдены?
        return True
    
    def send_test_notification(self, closed_item, trade_data=None):
        """Отправить тестовое уведомление"""
        print("\n  📨 ПРОВЕРКА ОТПРАВКИ УВЕДОМЛЕНИЯ:")
        
        if not trade_data:
            print("  ❌ Нет данных о сделке")
            return False
        
        try:
            # Формируем данные для уведомления
            notification_data = {
                "bot_name": self.bot["name"] if self.bot else "TEST",
                "symbol": closed_item.get("symbol"),
                "side": trade_data.get("side", "UNKNOWN"),
                "entry_price": float(trade_data.get("entry_price", 0)),
                "exit_price": float(closed_item.get("exit_price", 0)),
                "quantity": float(trade_data.get("quantity", 0)),
                "pnl": float(closed_item.get("pnl", 0)),
                "pnl_percent": 0,  # можно рассчитать
                "reason": "TEST",
                "balance": self.exchange.get_balance() or 0,
                "symbol_pnl": 0,
                "total_pnl": 0,
                "strategy_name": self.bot.get("strategy_type", "unknown") if self.bot else "unknown",
                "entry_time": trade_data.get("entry_time", datetime.now()),
                "order_id": closed_item.get("order_id")
            }
            
            print(f"  📤 Отправка уведомления...")
            print(f"  📊 Данные: {notification_data}")
            
            result = notifier.send_close_notification(notification_data)
            print(f"  ✅ Результат отправки: {result}")
            return result
            
        except Exception as e:
            print(f"  ❌ Ошибка при отправке: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_once(self):
        """Один цикл проверки"""
        print("\n" + "="*70)
        print(f"🔄 ЦИКЛ ПРОВЕРКИ [{datetime.now().strftime('%H:%M:%S')}]")
        print("="*70)
        
        # 1. Получаем данные с биржи
        closed_positions = self.get_closed_positions_from_exchange()
        
        # 2. Анализируем каждую позицию
        for item in closed_positions:
            order_id = item.get("order_id")
            if not order_id:
                continue
            
            print(f"\n▶️ Анализ ордера {order_id[:8]}...")
            
            # 3. Проверяем, обрабатывали ли мы этот ордер раньше
            if order_id in self.processed_orders:
                print(f"  ⏭️ Ордер уже был обработан в этом тесте")
                continue
            
            # 4. Проверяем все фильтры
            self.check_all_filters(item)
            
            # 5. Ищем сделку в БД
            trade = self.check_database_for_trade(order_id)
            
            # 6. Если нашли сделку, пробуем отправить уведомление
            if trade:
                print(f"\n  🎯 НАЙДЕНА СДЕЛКА ДЛЯ УВЕДОМЛЕНИЯ!")
                self.send_test_notification(item, trade)
                self.processed_orders.add(order_id)
            else:
                print(f"\n  ⏳ Сделка для уведомления не найдена")
    
    def run_loop(self, interval=10):
        """Запустить бесконечный цикл проверки"""
        print(f"\n🚀 Запуск цикла проверки каждые {interval} секунд")
        print("Нажмите Ctrl+C для остановки\n")
        
        try:
            while True:
                self.run_once()
                print(f"\n⏳ Ожидание {interval} секунд...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n👋 Тестер остановлен")
            print(f"📊 Всего обработано ордеров: {len(self.processed_orders)}")


if __name__ == "__main__":
    # Парсим аргументы командной строки
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ETHUSDT", help="Символ для отслеживания")
    parser.add_argument("--interval", type=int, default=10, help="Интервал опроса (сек)")
    args = parser.parse_args()
    
    tester = ClosedPositionsTester(args.symbol)
    tester.run_loop(args.interval)