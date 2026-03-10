#!/usr/bin/env python3
"""
Бот для торговли XRPUSDT.
Параметры из старой системы: MA (42, 79)
"""

import sys
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

# Принудительно добавляем проект в PYTHONPATH
os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent) + ":" + os.environ.get("PYTHONPATH", "")

from src.core.base_bot import TradingBot


class XRPUSDTBot(TradingBot):
    """Бот для торговли XRPUSDT"""
    
    def __init__(self):
        config = {
            'exchange': 'bybit',
            'symbol': 'XRPUSDT',
            
            # Торговые параметры (из старой системы)
            'tp': 0.040,  # 4.0%
            'sl': 0.100,  # 10.0% (очень большой SL!)
            'timeframe': 5,
            'qty': 10,
            'leverage': 1,
            'max_positions': 1,
            
            # Стратегия MA crossover (длинные MA)
            'strategy': 'ma_crossover',
            'strategy_params': {
                'short_ma': 42,
                'long_ma': 79
            },
            
            'risk_params': {
                'max_drawdown': 5.0,
                'max_consecutive_losses': 3,
                'max_daily_loss': 30.0,
                'max_position_size': 50.0
            },
            
            'intervals': {
                'status_log': 300,
                'risk_check': 60,
                'closed_check': 30,
                'snapshot': 3600
            }
        }
        
        super().__init__('XRPUSDT', config)


if __name__ == "__main__":
    bot = XRPUSDTBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()