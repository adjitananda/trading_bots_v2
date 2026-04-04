"""
Модуль для проверки триггеров ухудшения метрик.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import db

logger = logging.getLogger(__name__)

# Пороговые значения по умолчанию
DEFAULT_THRESHOLDS = {
    'max_drawdown': 10.0,      # 10%
    'sharpe_ratio': 1.0,       # < 1.0
    'win_rate': 40.0,          # < 40%
    'profit_factor': 1.2       # < 1.2
}


def check_triggers(bot_id: int, symbol: str, thresholds: Dict = None) -> Tuple[bool, List[str]]:
    """
    Проверить, превышены ли пороговые значения метрик.
    
    Args:
        bot_id: ID бота
        symbol: Торговый символ
        thresholds: Словарь с порогами (опционально)
    
    Returns:
        (triggered, reasons) - triggered=True если нужно запустить оптимизацию,
        reasons - список нарушенных метрик
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    
    # Получаем последние метрики
    query = """
        SELECT metric_date, total_trades, win_rate, sharpe_ratio, 
               max_drawdown, profit_factor, sortino_ratio, calmar_ratio
        FROM bot_performance_metrics
        WHERE bot_id = %s AND symbol = %s
        ORDER BY metric_date DESC
        LIMIT 1
    """
    
    result = db.execute_query(query, (bot_id, symbol))
    
    if not result:
        logger.info(f"Нет данных по метрикам для бота {bot_id}, символа {symbol}")
        return False, []
    
    metrics = result[0]
    total_trades = metrics.get('total_trades', 0)
    
    # Недостаточно данных для анализа
    if total_trades < 10:
        logger.info(f"Недостаточно сделок для бота {bot_id}, {symbol}: {total_trades}")
        return False, []
    
    triggered = False
    reasons = []
    
    # Проверка Max Drawdown
    dd = float(metrics.get('max_drawdown', 0))
    if dd > thresholds['max_drawdown']:
        triggered = True
        reasons.append(f"Max Drawdown = {dd:.2f}% (порог {thresholds['max_drawdown']}%)")
    
    # Проверка Sharpe Ratio
    sharpe = metrics.get('sharpe_ratio')
    if sharpe is not None and sharpe < thresholds['sharpe_ratio']:
        triggered = True
        reasons.append(f"Sharpe Ratio = {sharpe:.2f} (порог {thresholds['sharpe_ratio']})")
    
    # Проверка Win Rate
    wr = metrics.get('win_rate', 0)
    if wr < thresholds['win_rate']:
        triggered = True
        reasons.append(f"Win Rate = {wr:.1f}% (порог {thresholds['win_rate']}%)")
    
    # Проверка Profit Factor
    pf = metrics.get('profit_factor')
    if pf is not None and pf < thresholds['profit_factor']:
        triggered = True
        reasons.append(f"Profit Factor = {pf:.2f} (порог {thresholds['profit_factor']})")
    
    if triggered:
        logger.warning(f"🔔 Триггер сработал для {symbol}: {', '.join(reasons)}")
    else:
        logger.debug(f"✅ Метрики {symbol} в норме")
    
    return triggered, reasons


def create_alert(bot_id: int, symbol: str, reasons: List[str]) -> int:
    """
    Создать запись в таблице alerts о срабатывании триггера.
    
    Args:
        bot_id: ID бота
        symbol: Символ
        reasons: Список причин
    
    Returns:
        ID созданного алерта
    """
    message = f"Автооптимизация: {', '.join(reasons)}"
    
    query = """
        INSERT INTO alerts (bot_id, level, type, message, acknowledged, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    
    alert_id = db.execute_update(query, (bot_id, 'WARNING', 'optimization_trigger', message, 0))
    
    logger.info(f"📝 Создан алерт #{alert_id} для бота {bot_id}, символа {symbol}")
    return alert_id


def get_all_active_symbols() -> List[Dict]:
    """
    Получить все активные символы всех ботов.
    
    Returns:
        Список словарей с полями bot_id, bot_name, symbol
    """
    query = """
        SELECT b.id as bot_id, b.name as bot_name, bs.symbol
        FROM bot_symbols bs
        JOIN bots b ON b.id = bs.bot_id
        WHERE bs.is_active = 1 AND b.is_active = 1
    """
    return db.execute_query(query) or []


def check_all_bots() -> List[Dict]:
    """
    Проверить все активные символы всех ботов.
    
    Returns:
        Список сработавших триггеров с деталями
    """
    symbols = get_all_active_symbols()
    triggers = []
    
    for item in symbols:
        triggered, reasons = check_triggers(item['bot_id'], item['symbol'])
        if triggered:
            alert_id = create_alert(item['bot_id'], item['symbol'], reasons)
            triggers.append({
                'bot_id': item['bot_id'],
                'bot_name': item['bot_name'],
                'symbol': item['symbol'],
                'reasons': reasons,
                'alert_id': alert_id
            })
    
    return triggers


if __name__ == "__main__":
    # Тестовый запуск
    logging.basicConfig(level=logging.INFO)
    triggers = check_all_bots()
    print(f"Найдено триггеров: {len(triggers)}")
    for t in triggers:
        print(f"  {t['bot_name']} {t['symbol']}: {t['reasons']}")
