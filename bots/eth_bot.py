#!/usr/bin/env python3
"""
Бот для торговли ETHUSDT.
"""

import sys
from pathlib import Path
import os

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

# Принудительно добавляем проект в PYTHONPATH
os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent) + ":" + os.environ.get("PYTHONPATH", "")

from src.core.base_bot import TradingBot


class ETHUSDTBot(TradingBot):
    """Бот для торговли ETHUSDT"""
    
    def __init__(self):
        config = {
            # Биржа
            'exchange': 'bybit',
            'symbol': 'ETHUSDT',
            
            # Торговые параметры
            'tp': 0.035,  # 3.5%
            'sl': 0.030,  # 3.0%
            'timeframe': 5,  # 5 минут
            'qty': 10,  # 10 USDT
            'leverage': 1,
            'max_positions': 5,  # только одна позиция
            
            # Стратегия
            'strategy': 'ma_crossover',
            'strategy_params': {
                'short_ma': 10,
                'long_ma': 26
            },
            
            # Риск-параметры
            'risk_params': {
                'max_drawdown': 5.0,  # 5%
                'max_consecutive_losses': 3,
                'max_daily_loss': 30.0,  # 30 USDT
                'max_position_size': 100.0  # 100 USDT
            },
            
            # Интервалы (в секундах)
            'intervals': {
                'status_log': 300,    # 5 минут
                'risk_check': 60,      # 1 минута
                'closed_check': 30,    # 30 секунд
                'snapshot': 3600       # 1 час
            }
        }
        
        super().__init__('ETHUSDT', config)


if __name__ == "__main__":
    bot = ETHUSDTBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)