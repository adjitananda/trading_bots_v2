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
    
    for table in ['bot_symbols', 'bot_performance_metrics', 'optimization_history', 
                  'market_regime_log', 'trigger_log']:
        result = db.execute_query(f"SHOW TABLES LIKE '{table}'")
        if result:
            logger.info(f"  ✅ Таблица {table} существует")
        else:
            logger.warning(f"  ⚠️ Таблица {table} не найдена")
    
    exchanges = db.execute_query("SELECT id, name, is_active FROM exchanges")
    logger.info(f"  ✅ Биржи: {', '.join([e['name'] for e in exchanges])}")


def check_adapters():
    """Проверка адаптеров бирж"""
    logger.info("\n🔄 ПРОВЕРКА АДАПТЕРОВ БИРЖ:")
    
    try:
        adapter = get_exchange_by_name("bybit")
        logger.info("  ✅ BybitAdapter создан")
        
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
    
    if metrics.get('win_rate'):
        logger.info(f"  ✅ Метрики работают: Win Rate={metrics['win_rate']:.1f}%")
    else:
        logger.warning("  ⚠️ Проблемы с метриками")


def check_telegram_commands():
    """Проверка наличия команд в commander.py"""
    logger.info("\n📱 ПРОВЕРКА TELEGRAM КОМАНД:")
    
    commander_path = Path("/home/trader/trading_bots_v2/src/telegram/commander.py")
    
    if not commander_path.exists():
        logger.error("  ❌ commander.py не найден")
        return
    
    content = commander_path.read_text()
    
    commands = ['cmd_params', 'cmd_symbols', 'cmd_optimize', 'cmd_regime', 
                'cmd_risk_status', 'cmd_compare_strategies', 'cmd_reset_risk', 
                'cmd_cancel_optimization']
    
    found = [cmd for cmd in commands if cmd in content]
    missing = [cmd for cmd in commands if cmd not in content]
    
    if missing:
        logger.warning(f"  ⚠️ Отсутствуют команды: {missing}")
    else:
        logger.info(f"  ✅ Все команды добавлены: {len(found)} шт.")


def check_market_regime():
    """Проверка Market Regime детектора"""
    logger.info("\n🌊 ПРОВЕРКА MARKET REGIME:")
    
    try:
        from src.regime.detector import MarketRegimeDetector
        from src.trading.exchange_client import ExchangeClient
        
        exchange = ExchangeClient('bybit')
        detector = MarketRegimeDetector(exchange)
        
        regime, meta = detector.detect('ETHUSDT')
        logger.info(f"  ✅ Detector работает: режим ETHUSDT = {regime.value}")
        
    except Exception as e:
        logger.error(f"  ❌ Ошибка: {e}")


def check_risk_manager():
    """Проверка Risk Manager"""
    logger.info("\n🛡️ ПРОВЕРКА RISK MANAGER:")
    
    try:
        from src.optimizer.risk_manager import VolatilityGuard
        from src.trading.exchange_client import ExchangeClient
        
        exchange = ExchangeClient('bybit')
        vg = VolatilityGuard(exchange)
        activated, factor = vg.check('ETHUSDT')
        logger.info(f"  ✅ VolatilityGuard: фактор={factor}")
        
    except Exception as e:
        logger.error(f"  ❌ Ошибка: {e}")


def check_strategies():
    """Проверка всех 3 стратегий"""
    logger.info("\n📈 ПРОВЕРКА СТРАТЕГИЙ:")
    
    try:
        from src.strategies.legacy import StrategyFactory
        
        strategies = ['ma_crossover', 'bollinger', 'supertrend']
        
        for strategy in strategies:
            try:
                StrategyFactory.create_strategy(strategy, {})
                logger.info(f"  ✅ {strategy} - загружена")
            except Exception as e:
                logger.error(f"  ❌ {strategy} - ошибка: {e}")
                
    except Exception as e:
        logger.error(f"  ❌ Ошибка: {e}")


def check_optimization():
    """Проверка системы оптимизации"""
    logger.info("\n🔧 ПРОВЕРКА ОПТИМИЗАЦИИ:")
    
    result = subprocess.run(["pgrep", "-f", "trigger_daemon.py"], capture_output=True)
    if result.returncode == 0:
        logger.info("  ✅ trigger_daemon.py запущен")
    else:
        logger.warning("  ⚠️ trigger_daemon.py не запущен")
    
    try:
        from src.optimizer.param_optimizer import ParamOptimizer
        from src.optimizer.param_spaces import get_available_strategies
        
        strategies = get_available_strategies()
        logger.info(f"  ✅ ParamOptimizer доступен (стратегии: {strategies})")
    except Exception as e:
        logger.error(f"  ❌ Ошибка: {e}")


def check_reload_flag():
    """Проверка работы reload_flag"""
    logger.info("\n🔄 ПРОВЕРКА RELOAD_FLAG:")
    
    result = db.execute_query("""
        SELECT bot_id, symbol, reload_flag 
        FROM bot_symbols 
        WHERE is_active = 1 
        LIMIT 1
    """)
    
    if not result:
        logger.warning("  ⚠️ Нет активных символов для проверки")
        return
    
    bot_id = result[0]['bot_id']
    symbol = result[0]['symbol']
    
    db.execute_update(
        "UPDATE bot_symbols SET reload_flag = 1 WHERE bot_id = %s AND symbol = %s",
        (bot_id, symbol)
    )
    
    check = db.execute_query(
        "SELECT reload_flag FROM bot_symbols WHERE bot_id = %s AND symbol = %s",
        (bot_id, symbol)
    )
    
    if check and check[0]['reload_flag'] == 1:
        logger.info(f"  ✅ reload_flag для {symbol} успешно установлен в 1")
    else:
        logger.error(f"  ❌ Не удалось установить reload_flag для {symbol}")
    
    db.execute_update(
        "UPDATE bot_symbols SET reload_flag = 0 WHERE bot_id = %s AND symbol = %s",
        (bot_id, symbol)
    )
    logger.info(f"  ✅ reload_flag для {symbol} сброшен в 0")


def check_symbol_validation():
    """Проверка валидации символов"""
    logger.info("\n✅ ПРОВЕРКА ВАЛИДАЦИИ СИМВОЛОВ:")
    
    try:
        from src.trading.exchange_client import ExchangeClient
        from src.utils.symbol_validator import validate_symbol
        
        client = ExchangeClient("bybit")
        
        test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSD"]
        for sym in test_symbols:
            valid, msg = validate_symbol(client, sym)
            if valid:
                logger.info(f"  ✅ {sym}: валиден")
            else:
                logger.warning(f"  ⚠️ {sym}: {msg[:60]}")
        
        valid, msg = validate_symbol(client, "INVALID_SYMBOL_XYZ")
        if not valid:
            logger.info(f"  ✅ Невалидный символ корректно отклонён: {msg[:60]}")
        
        logger.info("  ✅ Валидатор символов работает")
    except Exception as e:
        logger.error(f"  ❌ Ошибка валидатора: {e}")


def check_overfit_interpretation():
    """Проверка интерпретации overfit_ratio"""
    logger.info("\n📊 ПРОВЕРКА OVERFIT_RATIO:")
    
    result = db.execute_query("DESCRIBE optimization_history")
    columns = [r['Field'] for r in result]
    
    required = ['test_sharpe', 'overfit_ratio']
    for col in required:
        if col in columns:
            logger.info(f"  ✅ Колонка {col} существует")
        else:
            logger.warning(f"  ⚠️ Колонка {col} не найдена")
    
    bad_values = db.execute_query(
        "SELECT COUNT(*) as cnt FROM optimization_history WHERE overfit_ratio = 999"
    )
    if bad_values and bad_values[0]['cnt'] > 0:
        logger.warning(f"  ⚠️ Найдено {bad_values[0]['cnt']} записей с overfit_ratio=999")
    else:
        logger.info("  ✅ Нет записей с некорректным overfit_ratio=999")
    
    bad_sharpe = db.execute_query(
        "SELECT COUNT(*) as cnt FROM optimization_history WHERE test_sharpe = -1"
    )
    if bad_sharpe and bad_sharpe[0]['cnt'] > 0:
        logger.warning(f"  ⚠️ Найдено {bad_sharpe[0]['cnt']} записей с test_sharpe = -1")
    else:
        logger.info("  ✅ Нет записей с test_sharpe = -1")


def check_trading_lib():
    """Проверка наличия trading_lib"""
    logger.info("\n📚 ПРОВЕРКА TRADING_LIB:")
    
    try:
        import trading_lib
        logger.info("  ✅ trading_lib импортируется")
        
        from trading_lib.exchanges import BybitAdapter, TinkoffAdapter, MoexAdapter
        logger.info("  ✅ BybitAdapter, TinkoffAdapter, MoexAdapter доступны")
    except ImportError as e:
        logger.error(f"  ❌ Ошибка: {e}")


def check_new_bots():
    """Проверка статуса новых ботов"""
    logger.info("\n🤖 ПРОВЕРКА НОВЫХ БОТОВ:")
    
    bots = ['CRYPTO_BOT', 'TINKOFF_BOT', 'MOEX_BOT']
    
    for bot_name in bots:
        result = db.execute_query(
            "SELECT id, status FROM bots WHERE name = %s",
            (bot_name,)
        )
        if result:
            status = result[0]['status']
            status_icon = "✅" if status == "active" else "⚠️"
            logger.info(f"  {status_icon} {bot_name}: {status}")
        else:
            logger.warning(f"  ⚠️ {bot_name}: не найден в БД")


def check_exchange_adapters_new():
    """Проверка новых адаптеров"""
    logger.info("\n🔄 ПРОВЕРКА НОВЫХ АДАПТЕРОВ:")
    
    try:
        from trading_lib.exchanges import TinkoffAdapter, MoexAdapter
        
        tinkoff = TinkoffAdapter()
        if tinkoff.test_connection():
            logger.info("  ✅ Тинькофф: токен установлен")
        else:
            logger.warning("  ⚠️ Тинькофф: токен не установлен")
        
        moex = MoexAdapter()
        if moex.test_connection():
            logger.info("  ✅ Мосбиржа: ISS API доступен")
        else:
            logger.warning("  ⚠️ Мосбиржа: проблемы с API")
            
    except Exception as e:
        logger.error(f"  ❌ Ошибка: {e}")


def main():
    logger.info("=" * 50)
    logger.info("🔧 ДИАГНОСТИКА СИСТЕМЫ TRADING_BOTS_V2")
    logger.info("=" * 50)
    
    check_database()
    check_adapters()
    check_metrics()
    check_telegram_commands()
    check_market_regime()
    check_risk_manager()
    check_strategies()
    check_optimization()
    check_reload_flag()
    check_symbol_validation()
    check_overfit_interpretation()
    check_trading_lib()
    check_new_bots()
    check_exchange_adapters_new()
    
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
