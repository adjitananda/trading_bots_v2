#!/usr/bin/env python3
"""
Миграционный скрипт: перенос данных из старых ботов в таблицу bot_symbols.
Каждый существующий бот → одна запись в bot_symbols с его symbol и strategy_params.
"""

import sys
import json
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import db
import logging

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def migrate():
    """Выполнить миграцию данных в bot_symbols"""
    
    logger.info("🚀 Начинаем миграцию данных в bot_symbols...")
    
    # Получаем всех активных ботов
    bots = db.execute_query("""
        SELECT id, name, strategy_type, strategy_params, risk_params 
        FROM bots 
        WHERE is_active = 1 AND status != 'stopped'
    """)
    
    if not bots:
        logger.warning("⚠️ Активных ботов не найдено")
        return
    
    logger.info(f"📊 Найдено {len(bots)} активных ботов")
    
    inserted = 0
    skipped = 0
    
    for bot in bots:
        bot_id = bot['id']
        bot_name = bot['name']
        
        # Определяем символ из имени бота (например ETHUSDT из ETHUSDTBot или eth_bot)
        # Пробуем разные варианты
        symbol = None
        
        # Вариант 1: имя бота содержит символ (BTCUSDT, ETHUSDT и т.д.)
        common_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOGEUSDT', 'LTCUSDT', 'SOLUSDT', 'XRPUSDT']
        for sym in common_symbols:
            if sym in bot_name.upper():
                symbol = sym
                break
        
        # Вариант 2: имя бота заканчивается на _bot (например eth_bot)
        if not symbol and bot_name.lower().endswith('_bot'):
            base = bot_name[:-4].upper()
            if base in ['BTC', 'ETH', 'ADA', 'DOGE', 'LTC', 'SOL', 'XRP']:
                symbol = f"{base}USDT"
        
        # Вариант 3: используем имя бота как есть (если похоже на символ)
        if not symbol and bot_name.upper() in common_symbols:
            symbol = bot_name.upper()
        
        # Вариант 4: если ничего не подошло, пропускаем
        if not symbol:
            logger.warning(f"⚠️ Не удалось определить символ для бота {bot_name} (id={bot_id}), пропускаем")
            skipped += 1
            continue
        
        # Подготавливаем strategy_params
        strategy_params = bot.get('strategy_params')
        if isinstance(strategy_params, str):
            try:
                strategy_params = json.loads(strategy_params)
            except:
                strategy_params = {}
        elif strategy_params is None:
            strategy_params = {}
        
        # Подготавливаем risk_params
        risk_params = bot.get('risk_params')
        if isinstance(risk_params, str):
            try:
                risk_params = json.loads(risk_params)
            except:
                risk_params = {}
        
        # Проверяем, существует ли уже запись
        existing = db.execute_query(
            "SELECT id FROM bot_symbols WHERE bot_id = %s AND symbol = %s",
            (bot_id, symbol)
        )
        
        if existing:
            logger.info(f"⏭️ Запись для бота {bot_name} (id={bot_id}) и символа {symbol} уже существует, пропускаем")
            skipped += 1
            continue
        
        # Вставляем запись
        try:
            db.execute_update("""
                INSERT INTO bot_symbols (bot_id, symbol, strategy_params, risk_params, is_active)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                bot_id,
                symbol,
                json.dumps(strategy_params),
                json.dumps(risk_params) if risk_params else None,
                True
            ))
            inserted += 1
            logger.info(f"✅ Добавлен символ {symbol} для бота {bot_name} (id={bot_id})")
        except Exception as e:
            logger.error(f"❌ Ошибка при вставке для бота {bot_name}: {e}")
    
    logger.info(f"🎉 Миграция завершена: вставлено {inserted}, пропущено {skipped}")
    
    # Показываем результат
    total = db.execute_query("SELECT COUNT(*) as count FROM bot_symbols")
    logger.info(f"📊 Итоговое количество записей в bot_symbols: {total[0]['count'] if total else 0}")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
