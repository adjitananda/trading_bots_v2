"""
Parameter Updater - обновление параметров стратегии в БД и уведомление бота.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import db

logger = logging.getLogger(__name__)


def update_params(bot_id: int, symbol: str, new_params: Dict[str, Any], 
                  history_id: int = None) -> bool:
    """
    Обновить параметры стратегии в таблице bot_symbols.
    
    Args:
        bot_id: ID бота
        symbol: Торговый символ
        new_params: Новые параметры стратегии
        history_id: ID записи в optimization_history (для связи)
    
    Returns:
        True если успешно, иначе False
    """
    try:
        # Получаем текущие параметры для бэкапа
        current = db.execute_query("""
            SELECT strategy_params FROM bot_symbols
            WHERE bot_id = %s AND symbol = %s
        """, (bot_id, symbol))
        
        current_params = current[0]['strategy_params'] if current else {}
        if isinstance(current_params, str):
            current_params = json.loads(current_params)
        
        # Обновляем параметры и устанавливаем reload_flag
        new_params_json = json.dumps(new_params)
        
        db.execute_update("""
            UPDATE bot_symbols 
            SET strategy_params = %s, reload_flag = 1, updated_at = NOW()
            WHERE bot_id = %s AND symbol = %s
        """, (new_params_json, bot_id, symbol))
        
        logger.info(f"✅ Обновлены параметры для {symbol} (бот {bot_id})")
        logger.info(f"   Старые: {current_params}")
        logger.info(f"   Новые: {new_params}")
        
        # Обновляем запись в optimization_history
        if history_id:
            db.execute_update("""
                UPDATE optimization_history 
                SET applied = TRUE, applied_at = NOW(), old_params = %s
                WHERE id = %s
            """, (json.dumps(current_params), history_id))
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления параметров: {e}")
        return False


def reject_params(history_id: int, reason: str = None) -> bool:
    """
    Отклонить предложенные параметры.
    
    Args:
        history_id: ID записи в optimization_history
        reason: Причина отклонения
    
    Returns:
        True если успешно
    """
    try:
        db.execute_update("""
            UPDATE optimization_history 
            SET rejected = TRUE, rejected_reason = %s
            WHERE id = %s
        """, (reason, history_id))
        
        logger.info(f"❌ Отклонены параметры (история #{history_id}): {reason}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отклонения: {e}")
        return False


def get_pending_optimizations() -> list:
    """
    Получить список неприменённых и неотклонённых оптимизаций.
    
    Returns:
        Список словарей с данными оптимизаций
    """
    query = """
        SELECT h.id, h.bot_id, h.symbol, h.best_sharpe, h.best_params, 
               h.trigger_reason, h.trials_count, b.name as bot_name,
               bs.strategy_params as current_params
        FROM optimization_history h
        JOIN bots b ON b.id = h.bot_id
        JOIN bot_symbols bs ON bs.bot_id = h.bot_id AND bs.symbol = h.symbol
        WHERE h.applied = FALSE AND h.rejected = FALSE
        ORDER BY h.optimization_start DESC
    """
    result = db.execute_query(query)
    
    if result:
        for r in result:
            if isinstance(r['best_params'], str):
                r['best_params'] = json.loads(r['best_params'])
            if isinstance(r['current_params'], str):
                r['current_params'] = json.loads(r['current_params'])
    
    return result or []


def check_reload_flag(bot_id: int, symbol: str) -> bool:
    """
    Проверить, есть ли сигнал на перезагрузку.
    
    Returns:
        True если нужно перезагрузить параметры
    """
    result = db.execute_query("""
        SELECT reload_flag FROM bot_symbols
        WHERE bot_id = %s AND symbol = %s
    """, (bot_id, symbol))
    
    if result and result[0].get('reload_flag', 0) == 1:
        return True
    return False


def clear_reload_flag(bot_id: int, symbol: str) -> bool:
    """
    Сбросить флаг перезагрузки.
    """
    db.execute_update("""
        UPDATE bot_symbols SET reload_flag = 0
        WHERE bot_id = %s AND symbol = %s
    """, (bot_id, symbol))
    return True


def get_risk_multiplier(bot_id: int, symbol: str) -> float:
    """
    Получить текущий множитель риска.
    """
    result = db.execute_query("""
        SELECT risk_multiplier FROM bot_symbols
        WHERE bot_id = %s AND symbol = %s
    """, (bot_id, symbol))
    
    if result and result[0].get('risk_multiplier'):
        return float(result[0]['risk_multiplier'])
    return 1.0


def set_risk_multiplier(bot_id: int, symbol: str, multiplier: float, reason: str = None) -> bool:
    """
    Установить множитель риска.
    """
    db.execute_update("""
        UPDATE bot_symbols 
        SET risk_multiplier = %s, updated_at = NOW()
        WHERE bot_id = %s AND symbol = %s
    """, (multiplier, bot_id, symbol))
    
    logger.info(f"📊 Risk multiplier для {symbol} установлен в {multiplier} (причина: {reason})")
    return True


def set_halted(bot_id: int, symbol: str, halted: bool) -> bool:
    """
    Установить статус остановки.
    """
    if halted:
        db.execute_update("""
            UPDATE bot_symbols 
            SET halted_at = NOW()
            WHERE bot_id = %s AND symbol = %s
        """, (bot_id, symbol))
    else:
        db.execute_update("""
            UPDATE bot_symbols 
            SET halted_at = NULL
            WHERE bot_id = %s AND symbol = %s
        """, (bot_id, symbol))
    return True


def is_halted(bot_id: int, symbol: str) -> bool:
    """
    Проверить, находится ли символ в состоянии остановки.
    """
    result = db.execute_query("""
        SELECT halted_at FROM bot_symbols
        WHERE bot_id = %s AND symbol = %s AND halted_at IS NOT NULL
    """, (bot_id, symbol))
    return len(result) > 0


def format_params_for_telegram(params: Dict) -> str:
    """Форматирует параметры для отправки в Telegram"""
    if not params:
        return "не указаны"
    
    parts = []
    for key, value in params.items():
        parts.append(f"{key}={value}")
    
    return ", ".join(parts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pending = get_pending_optimizations()
    print(f"Ожидающих оптимизаций: {len(pending)}")
    for p in pending:
        print(f"  #{p['id']}: {p['bot_name']} {p['symbol']} - Sharpe={p['best_sharpe']}")
