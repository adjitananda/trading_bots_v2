#!/usr/bin/env python3
"""
Фоновый процесс для мониторинга метрик и запуска оптимизации.
Запуск: python scripts/trigger_daemon.py &
"""

import sys
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer.triggers import check_all_bots
from src.core.database import db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/trader/trading_bots_v2/logs/trigger_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаём папку для логов
Path('/home/trader/trading_bots_v2/logs').mkdir(exist_ok=True)

CHECK_INTERVAL = 3600  # 1 час (в секундах)


def run_optimization(bot_id: int, symbol: str, reasons: list):
    """
    Запустить оптимизацию для символа.
    """
    logger.info(f"🚀 Запуск оптимизации для {symbol} (бот {bot_id})")
    logger.info(f"   Причины: {', '.join(reasons)}")
    
    # Запускаем param_optimizer.py как подпроцесс
    script_path = Path(__file__).parent / 'param_optimizer.py'
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), '--bot_id', str(bot_id), '--symbol', symbol],
            capture_output=True,
            text=True,
            timeout=300  # 5 минут максимум
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Оптимизация для {symbol} завершена успешно")
            logger.info(f"   Вывод: {result.stdout[-500:]}")
        else:
            logger.error(f"❌ Ошибка оптимизации для {symbol}: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ Таймаут оптимизации для {symbol}")
    except Exception as e:
        logger.error(f"❌ Исключение при запуске оптимизации: {e}")


def main():
    """Основной цикл демона"""
    logger.info("=" * 50)
    logger.info("🚀 TRIGGER DAEMON ЗАПУЩЕН")
    logger.info(f"   Интервал проверки: {CHECK_INTERVAL} сек (1 час)")
    logger.info("=" * 50)
    
    while True:
        try:
            logger.info("🔍 Проверка метрик всех ботов...")
            triggers = check_all_bots()
            
            if triggers:
                logger.info(f"⚠️ Найдено сработавших триггеров: {len(triggers)}")
                
                for trigger in triggers:
                    logger.info(f"   📊 {trigger['bot_name']} {trigger['symbol']}: {trigger['reasons']}")
                    
                    # Запускаем оптимизацию
                    run_optimization(
                        trigger['bot_id'],
                        trigger['symbol'],
                        trigger['reasons']
                    )
            else:
                logger.info("✅ Все метрики в норме, оптимизация не требуется")
            
            # Ждём следующий цикл
            logger.info(f"💤 Ожидание {CHECK_INTERVAL // 60} минут до следующей проверки...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки")
            break
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в демоне: {e}")
            time.sleep(60)  # Пауза перед перезапуском цикла


if __name__ == "__main__":
    main()
