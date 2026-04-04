#!/usr/bin/env python3
"""
Скрипт для расчёта метрик эффективности ботов.
Сохраняет результаты в таблицу bot_performance_metrics.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import db
from src.optimizer.metrics import calculate_all_metrics
import logging

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_closed_trades(bot_id: int, symbol: Optional[str] = None, days: int = 30) -> List[Dict]:
    """
    Получить закрытые сделки для бота за указанный период.
    
    Args:
        bot_id: ID бота
        symbol: Опционально - конкретный символ
        days: Количество дней (по умолчанию 30)
    
    Returns:
        Список сделок
    """
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    query = """
        SELECT id, symbol, side, entry_price, exit_price, quantity, 
               pnl, pnl_percent, entry_time, exit_time, exit_reason
        FROM trades
        WHERE bot_id = %s 
          AND status = 'closed'
          AND exit_time >= %s
    """
    params = [bot_id, start_date]
    
    if symbol:
        query += " AND symbol = %s"
        params.append(symbol)
    
    query += " ORDER BY exit_time"
    
    result = db.execute_query(query, tuple(params))
    return result if result else []


def save_metrics(bot_id: int, symbol: str, metric_date: str, metrics: Dict):
    """
    Сохранить метрики в БД.
    """
    try:
        db.execute_update("""
            INSERT INTO bot_performance_metrics 
            (bot_id, symbol, metric_date, total_pnl, total_trades, win_rate, 
             sharpe_ratio, max_drawdown, profit_factor, sortino_ratio, calmar_ratio)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            total_pnl = VALUES(total_pnl),
            total_trades = VALUES(total_trades),
            win_rate = VALUES(win_rate),
            sharpe_ratio = VALUES(sharpe_ratio),
            max_drawdown = VALUES(max_drawdown),
            profit_factor = VALUES(profit_factor),
            sortino_ratio = VALUES(sortino_ratio),
            calmar_ratio = VALUES(calmar_ratio)
        """, (
            bot_id, symbol, metric_date,
            metrics.get('total_pnl', 0),
            metrics.get('total_trades', 0),
            metrics.get('win_rate'),
            metrics.get('sharpe_ratio'),
            metrics.get('max_drawdown'),
            metrics.get('profit_factor'),
            metrics.get('sortino_ratio'),
            metrics.get('calmar_ratio')
        ))
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения метрик для {symbol}: {e}")
        return False


def calculate_for_bot(bot_id: int, days: int = 30):
    """
    Рассчитать метрики для всех символов бота.
    """
    # Получаем символы бота
    symbols_data = db.execute_query("""
        SELECT symbol FROM bot_symbols 
        WHERE bot_id = %s AND is_active = 1
    """, (bot_id,))
    
    if not symbols_data:
        # Старый режим: пытаемся определить символ из имени бота
        bot = db.execute_query("SELECT name FROM bots WHERE id = %s", (bot_id,))
        if bot:
            bot_name = bot[0]['name']
            # Пробуем извлечь символ из имени
            common_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOGEUSDT', 'LTCUSDT', 'SOLUSDT', 'XRPUSDT']
            for sym in common_symbols:
                if sym in bot_name.upper():
                    symbols_data = [{'symbol': sym}]
                    break
    
    if not symbols_data:
        logger.warning(f"⚠️ Бот {bot_id}: нет символов для расчёта")
        return
    
    metric_date = datetime.now().strftime('%Y-%m-%d')
    
    for row in symbols_data:
        symbol = row['symbol']
        
        # Получаем сделки
        trades = get_closed_trades(bot_id, symbol, days)
        
        if len(trades) < 3:
            logger.info(f"📊 Бот {bot_id}, {symbol}: недостаточно сделок ({len(trades)})")
            continue
        
        # Рассчитываем метрики
        metrics = calculate_all_metrics(trades)
        
        # Сохраняем
        if save_metrics(bot_id, symbol, metric_date, metrics):
            logger.info(f"✅ Бот {bot_id}, {symbol}: {metrics['total_trades']} сделок, "
                       f"Win Rate={metrics.get('win_rate', 0):.1f}%, "
                       f"Max DD={metrics.get('max_drawdown', 0):.1f}%")
        else:
            logger.error(f"❌ Ошибка сохранения для {bot_id}, {symbol}")


def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Расчёт метрик ботов')
    parser.add_argument('--bot_id', type=int, help='ID конкретного бота')
    parser.add_argument('--symbol', type=str, help='Конкретный символ (только с bot_id)')
    parser.add_argument('--days', type=int, default=30, help='Период в днях (по умолчанию 30)')
    parser.add_argument('--all', action='store_true', help='Рассчитать для всех активных ботов')
    
    args = parser.parse_args()
    
    logger.info("🚀 Запуск расчёта метрик...")
    
    if args.bot_id:
        # Конкретный бот
        if args.symbol:
            # Конкретный символ
            trades = get_closed_trades(args.bot_id, args.symbol, args.days)
            if len(trades) < 3:
                logger.warning(f"⚠️ Недостаточно сделок для {args.symbol}: {len(trades)}")
                return
            
            metrics = calculate_all_metrics(trades)
            metric_date = datetime.now().strftime('%Y-%m-%d')
            save_metrics(args.bot_id, args.symbol, metric_date, metrics)
            
            logger.info(f"📊 Результаты для {args.symbol}:")
            for k, v in metrics.items():
                if v is not None:
                    if isinstance(v, float):
                        logger.info(f"   {k}: {v:.4f}")
                    else:
                        logger.info(f"   {k}: {v}")
        else:
            # Весь бот
            calculate_for_bot(args.bot_id, args.days)
    elif args.all:
        # Все боты
        bots = db.execute_query("SELECT id, name FROM bots WHERE is_active = 1 AND id > 3")
        if not bots:
            logger.warning("⚠️ Активных ботов не найдено")
            return
        
        for bot in bots:
            logger.info(f"📊 Обработка бота {bot['name']} (id={bot['id']})")
            calculate_for_bot(bot['id'], args.days)
    else:
        # По умолчанию: для всех ботов
        bots = db.execute_query("SELECT id, name FROM bots WHERE is_active = 1 AND id > 3")
        for bot in bots:
            calculate_for_bot(bot['id'], args.days)
    
    logger.info("🎉 Расчёт метрик завершён")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
