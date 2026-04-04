#!/usr/bin/env python3
"""
Диагностический скрипт для проверки системы.
"""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import db
from src.exchanges.factory import get_exchange_by_name
from src.optimizer.metrics import calculate_all_metrics
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_database():
    """Проверка структуры БД"""
    logger.info("\n📁 ПРОВЕРКА БАЗЫ ДАННЫХ:")
    
    result = db.execute_query("SHOW TABLES LIKE 'bot_symbols'")
    if result:
        logger.info("  ✅ Таблица bot_symbols существует")
        count = db.execute_query("SELECT COUNT(*) as cnt FROM bot_symbols")
        logger.info(f"     Записей в bot_symbols: {count[0]['cnt']}")
    else:
        logger.error("  ❌ Таблица bot_symbols не найдена")
    
    result = db.execute_query("SHOW TABLES LIKE 'bot_performance_metrics'")
    if result:
        logger.info("  ✅ Таблица bot_performance_metrics существует")
        count = db.execute_query("SELECT COUNT(*) as cnt FROM bot_performance_metrics")
        logger.info(f"     Записей в метриках: {count[0]['cnt']}")
    else:
        logger.warning("  ⚠️ Таблица bot_performance_metrics не найдена")
    
    result = db.execute_query("SHOW TABLES LIKE 'optimization_history'")
    if result:
        logger.info("  ✅ Таблица optimization_history существует")
        count = db.execute_query("SELECT COUNT(*) as cnt FROM optimization_history")
        logger.info(f"     Записей в истории: {count[0]['cnt']}")
    else:
        logger.warning("  ⚠️ Таблица optimization_history не найдена")
    
    exchanges = db.execute_query("SELECT id, name, is_active FROM exchanges")
    logger.info(f"  ✅ Биржи: {', '.join([e['name'] for e in exchanges])}")


def check_adapters():
    """Проверка адаптеров бирж"""
    logger.info("\n🔄 ПРОВЕРКА АДАПТЕРОВ БИРЖ:")
    
    try:
        adapter = get_exchange_by_name("bybit")
        logger.info("  ✅ BybitAdapter создан")
        
        info = adapter.get_exchange_info()
        logger.info(f"     Информация: {info['name']} ({info['type']})")
        
        symbols = adapter.get_symbols()
        logger.info(f"     Доступно символов: {len(symbols)}")
        
        if adapter.test_connection():
            logger.info("  ✅ Подключение к Bybit работает")
        else:
            logger.warning("  ⚠️ Проблема с подключением к Bybit")
            
    except Exception as e:
        logger.error(f"  ❌ Ошибка адаптера: {e}")


def check_metrics():
    """Проверка расчёта метрик"""
    logger.info("\n📊 ПРОВЕРКА МЕТРИК:")
    
    test_trades = [
        {'pnl': 100, 'entry_time': '2025-01-01'},
        {'pnl': -50, 'entry_time': '2025-01-02'},
        {'pnl': 200, 'entry_time': '2025-01-03'},
    ]
    
    metrics = calculate_all_metrics(test_trades)
    
    required = ['win_rate', 'max_drawdown', 'sharpe_ratio', 'profit_factor']
    missing = [k for k in required if metrics.get(k) is None]
    
    if not missing:
        logger.info(f"  ✅ Метрики работают: Win Rate={metrics['win_rate']:.1f}%")
    else:
        logger.warning(f"  ⚠️ Проблемы с метриками: {missing}")


def check_bot_multi_coin():
    """Проверка multi-coin поддержки"""
    logger.info("\n🤖 ПРОВЕРКА MULTI-COIN:")
    
    query = """
        SELECT b.id, b.name, COUNT(bs.id) as symbol_count
        FROM bots b
        LEFT JOIN bot_symbols bs ON bs.bot_id = b.id AND bs.is_active = 1
        WHERE b.is_active = 1 AND b.id > 3
        GROUP BY b.id
        HAVING symbol_count > 0
    """
    bots = db.execute_query(query)
    
    if bots:
        multi = [b for b in bots if b['symbol_count'] > 1]
        if multi:
            logger.info(f"  ✅ Найдены multi-coin боты:")
            for b in multi:
                logger.info(f"     {b['name']}: {b['symbol_count']} символов")
        else:
            logger.info(f"  ✅ Боты готовы к multi-coin (сейчас по 1 символу)")
    else:
        logger.warning("  ⚠️ Нет ботов с символами")


def check_telegram_commands():
    """Проверка наличия новых команд в commander.py"""
    logger.info("\n📱 ПРОВЕРКА TELEGRAM КОМАНД:")
    
    commander_path = Path("/home/trader/trading_bots_v2/src/telegram/commander.py")
    
    if not commander_path.exists():
        logger.error("  ❌ commander.py не найден")
        return
    
    content = commander_path.read_text()
    
    commands = ['cmd_metrics', 'cmd_symbols', 'cmd_add_symbol', 'cmd_optimize', 
                'cmd_apply_params', 'cmd_reject_params']
    
    found = []
    missing = []
    
    for cmd in commands:
        if cmd in content:
            found.append(cmd)
        else:
            missing.append(cmd)
    
    if missing:
        logger.warning(f"  ⚠️ Отсутствуют команды: {missing}")
    else:
        logger.info(f"  ✅ Все команды добавлены: {len(found)} шт.")


def check_optimization():
    """Проверка системы оптимизации"""
    logger.info("\n🔧 ПРОВЕРКА ОПТИМИЗАЦИИ:")
    
    # Проверяем trigger_daemon.py
    result = subprocess.run(["pgrep", "-f", "trigger_daemon.py"], capture_output=True)
    if result.returncode == 0:
        logger.info("  ✅ trigger_daemon.py запущен")
    else:
        logger.warning("  ⚠️ trigger_daemon.py не запущен. Запустите: python scripts/trigger_daemon.py &")
    
    # Проверяем импорт оптимизатора
    try:
        from src.optimizer.param_optimizer import ParamOptimizer
        logger.info("  ✅ ParamOptimizer доступен")
    except Exception as e:
        logger.error(f"  ❌ ParamOptimizer не загружен: {e}")
    
    # Проверяем parameter_updater
    try:
        from src.optimizer.parameter_updater import get_pending_optimizations
        pending = get_pending_optimizations()
        logger.info(f"  ✅ ParameterUpdater работает (ожидающих: {len(pending)})")
    except Exception as e:
        logger.error(f"  ❌ ParameterUpdater ошибка: {e}")


def main():
    """Основная диагностика"""
    logger.info("=" * 50)
    logger.info("🔧 ДИАГНОСТИКА СИСТЕМЫ TRADING_BOTS_V2")
    logger.info("=" * 50)
    
    check_database()
    check_adapters()
    check_metrics()
    check_bot_multi_coin()
    check_telegram_commands()
    check_optimization()
    
    logger.info("\n" + "=" * 50)
    logger.info("✅ Диагностика завершена")
    logger.info("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
