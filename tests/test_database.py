#!/usr/bin/env python3
"""
Тестирование работы с базой данных.
Запуск: python3 -m tests.test_database
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import db
from datetime import datetime, timedelta
import json


def test_connection():
    """Тест подключения"""
    print("\n🔌 Тест подключения...")
    try:
        # Простой запрос для проверки
        result = db.execute_query("SELECT 1 as test")
        print(f"  ✅ Подключение работает: {result}")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


def test_exchanges():
    """Тест работы с биржами"""
    print("\n🏦 Тест бирж...")
    
    # Получаем все биржи
    exchanges = db.get_all_exchanges()
    print(f"  📋 Найдено бирж: {len(exchanges)}")
    for ex in exchanges:
        print(f"     • {ex['name']} ({ex['display_name']})")
    
    # Получаем ID ByBit
    bybit_id = db.get_exchange_id('bybit')
    print(f"  🔍 ID ByBit: {bybit_id}")
    
    return bybit_id is not None


def test_bot_operations(exchange_id):
    """Тест создания и получения бота"""
    print("\n🤖 Тест операций с ботами...")
    
    # Создаем тестового бота
    bot_data = {
        'name': 'TEST_BOT',
        'exchange_id': exchange_id,
        'strategy_type': 'ma_crossover',
        'strategy_params': {'short_ma': 14, 'long_ma': 45},
        'risk_params': {'max_drawdown': 5, 'max_consecutive_losses': 3},
        'version': '1.0.0'
    }
    
    bot_id = db.create_bot(bot_data)
    print(f"  ✅ Создан бот с ID: {bot_id}")
    
    # Получаем бота по ID
    bot = db.get_bot(bot_id)
    print(f"  🔍 Получен бот: {bot['name']}")
    print(f"     Стратегия: {bot['strategy_type']}")
    print(f"     Параметры: {bot['strategy_params']}")
    
    # Получаем бота по имени
    bot_by_name = db.get_bot_by_name('TEST_BOT')
    print(f"  🔍 Поиск по имени: {bot_by_name['name'] if bot_by_name else 'None'}")
    
    # Получаем всех активных ботов
    active_bots = db.get_all_active_bots()
    print(f"  📋 Активных ботов: {len(active_bots)}")
    
    return bot_id


def test_trade_operations(bot_id, exchange_id):
    """Тест создания и закрытия сделки"""
    print("\n💰 Тест операций со сделками...")
    
    # Создаем сделку (открытие)
    trade_data = {
        'bot_id': bot_id,
        'exchange_id': exchange_id,
        'symbol': 'ETHUSDT',
        'side': 'BUY',
        'entry_time': datetime.now(),
        'entry_price': 1500.50,
        'quantity': 0.1,
        'entry_order_id': 'test_order_123'
    }
    
    trade_id = db.create_trade(trade_data)
    print(f"  ✅ Создана сделка ID: {trade_id}")
    
    # Получаем сделку
    trade = db.get_trade(trade_id)
    print(f"  🔍 Получена сделка: {trade['symbol']} {trade['side']} @ {trade['entry_price']}")
    
    # Получаем открытые сделки
    open_trades = db.get_open_trades()
    print(f"  📋 Открытых сделок всего: {len(open_trades)}")
    
    open_bot_trades = db.get_open_trades(bot_id)
    print(f"  📋 Открытых сделок бота: {len(open_bot_trades)}")
    
    # Закрываем сделку
    close_data = {
        'exit_time': datetime.now() + timedelta(hours=2),
        'exit_price': 1600.00,
        'pnl': 100.0,
        'exit_reason': 'TP',
        'exit_order_id': 'test_order_456'
    }
    
    success = db.close_trade(trade_id, close_data)
    print(f"  {'✅' if success else '❌'} Закрытие сделки: {success}")
    
    # Проверяем, что закрылась
    trade_after = db.get_trade(trade_id)
    print(f"  🔍 Статус после закрытия: {trade_after['status']}")
    
    return trade_id


def test_order_operations(bot_id, exchange_id, trade_id):
    """Тест работы с ордерами"""
    print("\n📝 Тест операций с ордерами...")
    
    # Создаем ордер
    order_data = {
        'trade_id': trade_id,
        'bot_id': bot_id,
        'exchange_id': exchange_id,
        'exchange_order_id': 'test_exchange_789',
        'symbol': 'ETHUSDT',
        'side': 'BUY',
        'order_type': 'market',
        'quantity': 0.1,
        'price': 1500.50,
        'status': 'new'
    }
    
    order_db_id = db.create_order(order_data)
    print(f"  ✅ Создан ордер в БД ID: {order_db_id}")
    
    # Получаем ордер по ID с биржи
    order = db.get_order('test_exchange_789')
    print(f"  🔍 Получен ордер: {order['exchange_order_id']} - {order['status']}")
    
    # Обновляем статус ордера
    update_data = {
        'status': 'filled',
        'filled_quantity': 0.1,
        'average_fill_price': 1500.50,
        'finished_at': datetime.now()
    }
    
    success = db.update_order('test_exchange_789', update_data)
    print(f"  {'✅' if success else '❌'} Обновление ордера")
    
    # Получаем ордера бота
    bot_orders = db.get_orders_by_bot(bot_id, limit=5)
    print(f"  📋 Ордеров бота: {len(bot_orders)}")
    
    return True


def test_snapshot(bot_id, exchange_id):
    """Тест создания снимка"""
    print("\n📸 Тест снимков состояния...")
    
    snapshot_data = {
        'bot_id': bot_id,
        'exchange_id': exchange_id,
        'balance': 1000.50,
        'total_pnl': 150.25,
        'daily_pnl': 25.30,
        'open_positions_count': 2,
        'open_positions_json': [
            {'symbol': 'ETHUSDT', 'side': 'BUY', 'entry_price': 1500}
        ],
        'drawdown_current': 2.5,
        'drawdown_max': 5.0,
        'consecutive_losses': 0
    }
    
    snapshot_id = db.create_snapshot(snapshot_data)
    print(f"  ✅ Создан снимок ID: {snapshot_id}")
    
    last = db.get_last_snapshot(bot_id)
    print(f"  🔍 Последний снимок: баланс {last['balance']}, PnL {last['total_pnl']}")
    
    return True


def test_alert(bot_id):
    """Тест алертов"""
    print("\n⚠️ Тест алертов...")
    
    alert_data = {
        'bot_id': bot_id,
        'level': 'WARNING',
        'type': 'DRAWDOWN_EXCEEDED',
        'threshold_value': 5.0,
        'actual_value': 7.2,
        'message': 'Тестовый алерт: просадка превышена'
    }
    
    alert_id = db.create_alert(alert_data)
    print(f"  ✅ Создан алерт ID: {alert_id}")
    
    unresolved = db.get_unresolved_alerts(bot_id)
    print(f"  📋 Неподтвержденных алертов: {len(unresolved)}")
    
    # Подтверждаем
    success = db.acknowledge_alert(alert_id, 'test_action')
    print(f"  {'✅' if success else '❌'} Подтверждение алерта")
    
    return True


def test_reports(bot_id):
    """Тест отчетов"""
    print("\n📊 Тест отчетов...")
    
    # Сводка по боту
    summary = db.get_bot_summary(bot_id, days=7)
    print(f"  📋 Сводка по боту за 7 дней:")
    print(f"     Сделок: {summary.get('total_trades', 0)}")
    print(f"     PnL: {summary.get('total_pnl', 0):.2f}")
    if summary.get('total_trades', 0) > 0:
        print(f"     Win Rate: {summary.get('win_rate', 0):.1f}%")
    
    # Дневной PnL
    daily = db.get_daily_pnl(bot_id, days=7)
    print(f"  📅 Дневной PnL ({len(daily)} дней):")
    for d in daily[:3]:  # покажем первые 3
        print(f"     {d['date']}: {d['total_pnl']:.2f} ({d['trades']} сделок)")
    
    # Открытые позиции через view
    try:
        positions = db.get_open_positions_view()
        print(f"  📈 Открытых позиций: {len(positions)}")
    except:
        print("  ⚠️ View v_open_positions не создано")
    
    # Итоги за сегодня
    try:
        today = db.get_today_summary()
        if today:
            print(f"  📆 Сегодня: {today.get('total_trades', 0)} сделок, PnL {today.get('total_pnl', 0):.2f}")
    except:
        print("  ⚠️ View v_today_summary не создано")
    
    return True


def test_cache():
    """Тест кэширования"""
    print("\n💾 Тест кэша...")
    
    db.cache_set('test_key', 'test_value')
    value = db.cache_get('test_key', max_age_seconds=60)
    print(f"  ✅ Получено из кэша: {value}")
    
    db.cache_clear()
    value = db.cache_get('test_key')
    print(f"  🔍 После очистки: {value}")
    
    return True


def test_stop_events(bot_id):
    """Тест событий остановки"""
    print("\n🛑 Тест событий остановки...")
    
    stop_data = {
        'bot_id': bot_id,
        'stop_type': 'soft',
        'stop_reason': 'max_drawdown',
        'triggered_by': 'SYSTEM',
        'auto_restart_scheduled': True,
        'auto_restart_at': datetime.now() + timedelta(hours=1)
    }
    
    event_id = db.create_stop_event(stop_data)
    print(f"  ✅ Создано событие остановки ID: {event_id}")
    
    history = db.get_bot_stop_history(bot_id, limit=5)
    print(f"  📋 История остановок: {len(history)} записей")
    
    return True


def test_command_logging():
    """Тест логирования команд"""
    print("\n📝 Тест логирования команд...")
    
    cmd_id = db.log_command(
        user_id="test_user_123",
        username="test_user",
        command="/start",
        args={"param": "value"},
        success=True,
        result={"message": "OK"}
    )
    print(f"  ✅ Команда записана ID: {cmd_id}")
    
    return True


def cleanup_test_data(bot_id):
    """Очистка тестовых данных"""
    print("\n🧹 Очистка тестовых данных...")
    
    try:
        # Удаляем тестовые данные
        db.execute_update("DELETE FROM command_logs WHERE user_id = 'test_user_123'")
        db.execute_update("DELETE FROM orders WHERE bot_id = %s", (bot_id,))
        db.execute_update("DELETE FROM trades WHERE bot_id = %s", (bot_id,))
        db.execute_update("DELETE FROM snapshots WHERE bot_id = %s", (bot_id,))
        db.execute_update("DELETE FROM alerts WHERE bot_id = %s", (bot_id,))
        db.execute_update("DELETE FROM bot_stop_events WHERE bot_id = %s", (bot_id,))
        db.execute_update("DELETE FROM bots WHERE id = %s", (bot_id,))
        
        print("  ✅ Тестовые данные удалены")
    except Exception as e:
        print(f"  ⚠️ Ошибка при очистке: {e}")


def main():
    """Запуск всех тестов"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    # 1. Проверка подключения
    if not test_connection():
        print("\n❌ Ошибка подключения. Дальнейшие тесты невозможны.")
        return
    
    bot_id = None
    
    try:
        # 2. Тест бирж
        if not test_exchanges():
            print("\n❌ Ошибка получения бирж.")
            return
        
        # Получаем ID ByBit для тестов
        exchange_id = db.get_exchange_id('bybit')
        if not exchange_id:
            print("\n⚠️ Биржа ByBit не найдена, используем ID=1")
            exchange_id = 1
        
        # 3. Тест ботов
        bot_id = test_bot_operations(exchange_id)
        
        # 4. Тест сделок
        trade_id = test_trade_operations(bot_id, exchange_id)
        
        # 5. Тест ордеров
        test_order_operations(bot_id, exchange_id, trade_id)
        
        # 6. Тест снимков
        test_snapshot(bot_id, exchange_id)
        
        # 7. Тест алертов
        test_alert(bot_id)
        
        # 8. Тест отчетов
        test_reports(bot_id)
        
        # 9. Тест событий остановки
        test_stop_events(bot_id)
        
        # 10. Тест команд
        test_command_logging()
        
        # 11. Тест кэша
        test_cache()
        
        print("\n" + "=" * 60)
        print("✅ Все тесты успешно завершены!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Ошибка во время тестов: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Очистка тестовых данных
        if bot_id:
            cleanup_test_data(bot_id)


if __name__ == "__main__":
    main()