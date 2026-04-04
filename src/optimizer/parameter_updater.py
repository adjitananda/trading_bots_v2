"""
Parameter Updater - обновление параметров стратегии в БД и уведомление бота.
"""

import json
import logging
import os
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
        
        # Обновляем параметры
        new_params_json = json.dumps(new_params)
        
        db.execute_update("""
            UPDATE bot_symbols 
            SET strategy_params = %s, updated_at = NOW()
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
        
        # Отправляем сигнал боту на перезагрузку
        signal_file = f"/tmp/reload_{bot_id}_{symbol}.signal"
        with open(signal_file, 'w') as f:
            f.write(f"reload_params|{bot_id}|{symbol}|{datetime.now().isoformat()}")
        
        logger.info(f"📡 Отправлен сигнал перезагрузки: {signal_file}")
        
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


def format_params_for_telegram(params: Dict) -> str:
    """Форматирует параметры для отправки в Telegram"""
    if not params:
        return "не указаны"
    
    parts = []
    for key, value in params.items():
        parts.append(f"{key}={value}")
    
    return ", ".join(parts)


if __name__ == "__main__":
    # Тест
    logging.basicConfig(level=logging.INFO)
    pending = get_pending_optimizations()
    print(f"Ожидающих оптимизаций: {len(pending)}")
    for p in pending:
        print(f"  #{p['id']}: {p['bot_name']} {p['symbol']} - Sharpe={p['best_sharpe']}")
