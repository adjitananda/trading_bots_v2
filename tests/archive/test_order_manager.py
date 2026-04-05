#!/usr/bin/env python3
"""
Тестирование OrderManager и PositionTracker.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.exchange_client import ExchangeClient
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.core.database import db
import time


def test_order_manager():
    """Тест OrderManager"""
    print("\n📝 Тест OrderManager...")
    
    # Получаем первого активного бота
    bots = db.get_all_active_bots()
    if not bots:
        print("  ⚠️ Нет активных ботов для теста")
        # Создаем тестового бота
        exchange_id = db.get_exchange_id('bybit')
        if not exchange_id:
            print("  ❌ Биржа not found")
            return None, None
        
        bot_id = db.create_bot({
            'name': 'TEST_BOT',
            'exchange_id': exchange_id,
            'strategy_type': 'ma_crossover',
            'strategy_params': {'short_ma': 14, 'long_ma': 45},
            'risk_params': {'max_drawdown': 5}
        })
        bot = db.get_bot(bot_id)
    else:
        bot = bots[0]
        bot_id = bot['id']
    
    print(f"  Используем бота: {bot['name']} (ID: {bot_id})")
    
    # Создаем клиент биржи
    exchange = ExchangeClient('bybit')
    
    # Создаем менеджеры
    order_manager = OrderManager(exchange, bot_id, bot['name'])
    position_tracker = PositionTracker(exchange, bot_id, bot['name'])
    
    # Тест получения позиций
    print("\n  📊 Текущие позиции:")
    positions = position_tracker.get_current_positions()
    if positions:
        for pos in positions:
            print(f"    {pos['symbol']} {pos['side']}: {pos['size']} @ {pos['entry_price']}")
    else:
        print("    Нет открытых позиций")
    
    # Тест сводки
    summary = position_tracker.get_positions_summary()
    print(f"\n  📈 Сводка:")
    print(f"    Всего позиций: {summary['total_positions']}")
    print(f"    LONG: {summary['long_positions']}, SHORT: {summary['short_positions']}")
    print(f"    Нереал. PnL: {summary['total_pnl']:.2f}")
    
    # Тест PnL
    total_pnl = position_tracker.get_total_pnl()
    symbol_pnl = position_tracker.get_symbol_pnl()
    print(f"\n  💰 PnL:")
    print(f"    Общий: {total_pnl:.2f}")
    print(f"    По символу: {symbol_pnl:.2f}")
    
    # Тест создания снимка
    snapshot_id = position_tracker.create_snapshot()
    print(f"\n  📸 Создан снимок ID: {snapshot_id}")
    
    # Тест проверки рисков
    risk_params = {
        'max_drawdown': 5.0,
        'max_consecutive_losses': 3,
        'max_daily_loss': 50.0,
        'max_position_size': 1000.0
    }
    alerts = position_tracker.check_risk_limits(risk_params)
    if alerts:
        print(f"\n  ⚠️ Найдено нарушений: {len(alerts)}")
        for alert in alerts:
            print(f"    {alert['level']}: {alert['message']}")
    else:
        print(f"\n  ✅ Риск-параметры в норме")
    
    # Тест получения недавних ордеров
    recent = order_manager.get_recent_orders(limit=5)
    print(f"\n  📋 Недавних ордеров в БД: {len(recent)}")
    
    # Тест открытых сделок
    open_trades = order_manager.get_open_trades()
    print(f"  📋 Открытых сделок: {len(open_trades)}")
    
    return order_manager, position_tracker


def test_market_order(order_manager):
    """Тест размещения ордера (только для демо!)"""
    print("\n⚠️  ТЕСТ РАЗМЕЩЕНИЯ ОРДЕРА")
    print("    Нажмите Ctrl+C для отмены или Enter для продолжения...")
    try:
        input()
    except KeyboardInterrupt:
        print("  Тест пропущен")
        return
    
    print("\n  Размещаем тестовый ордер на очень малую сумму...")
    
    symbol = 'BTCUSDT'
    side = 'buy'
    
    try:
        # Рассчитываем минимальное количество
        price = order_manager.exchange.get_current_price(symbol)
        if not price:
            print("  ❌ Не удалось получить цену")
            return
        
        # Пытаемся купить на 5 USDT (минималка)
        qty = order_manager.exchange.calculate_quantity(symbol, 5, price)
        
        if qty < 0.0001:  # слишком мало
            qty = 0.0001  # минимальное для BTC
        
        print(f"  Попытка купить {qty} {symbol} по ~{price:.2f}")
        
        result = order_manager.place_market_order(
            symbol=symbol,
            side=side,
            quantity=qty,
            take_profit=price * 1.05,  # TP +5%
            stop_loss=price * 0.95,     # SL -5%
            tp_percent=5.0,
            sl_percent=5.0
        )
        
        if result['success']:
            print(f"  ✅ Ордер размещен: {result['order_id']}")
            print(f"  🆔 Trade ID: {result['trade_id']}")
            
            # Ждем немного и проверяем статус
            time.sleep(2)
            status = order_manager.check_order_status(result['order_id'])
            print(f"  📊 Статус ордера: {status.get('status', 'unknown')}")
            
            # Проверяем информацию о сделке
            trade_info = order_manager.get_trade_info(result['order_id'])
            if trade_info:
                print(f"  💰 Цена входа: {trade_info.get('entry_price')}")
            
        else:
            print(f"  ❌ Ошибка: {result.get('error')}")
            
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")


def test_closed_positions(order_manager):
    """Тест проверки закрытых позиций"""
    print("\n🔄 Тест проверки закрытых позиций...")
    
    closed = order_manager.check_closed_positions()
    
    if closed:
        print(f"  Найдено закрытых сделок: {len(closed)}")
        for item in closed:
            print(f"    {item['symbol']}: PnL {item['pnl']:.2f} ({item['pnl_percent']:.2f}%) - {item['reason']}")
    else:
        print("  Нет новых закрытых сделок")


def test_cancel_order(order_manager):
    """Тест отмены ордера (если есть открытые)"""
    print("\n❌ Тест отмены ордера...")
    
    # Получаем недавние ордера со статусом new
    recent = order_manager.get_recent_orders(limit=10)
    open_orders = [o for o in recent if o['status'] in ['new', 'partially_filled']]
    
    if not open_orders:
        print("  Нет открытых ордеров для отмены")
        return
    
    order = open_orders[0]
    print(f"  Отменяем ордер {order['exchange_order_id']} для {order['symbol']}")
    
    success = order_manager.cancel_order(order['symbol'], order['exchange_order_id'])
    if success:
        print("  ✅ Ордер отменен")
    else:
        print("  ❌ Ошибка отмены")


def main():
    """Запуск тестов"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ ORDER MANAGER")
    print("=" * 60)
    
    # Тест базовых функций
    order_manager, position_tracker = test_order_manager()
    
    if not order_manager:
        print("\n❌ Не удалось создать OrderManager")
        return
    
    # Тест проверки закрытых позиций
    test_closed_positions(order_manager)
    
    # Тест отмены ордера (опционально)
    # test_cancel_order(order_manager)
    
    # Тест размещения ордера (закомментировано для безопасности)
    # test_market_order(order_manager)
    
    print("\n" + "=" * 60)
    print("✅ Тесты завершены!")
    print("=" * 60)


if __name__ == "__main__":
    main()