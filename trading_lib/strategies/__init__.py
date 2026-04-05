"""
Стратегии для торговых ботов.
"""

from trading_lib.strategies.base import BaseStrategy
from trading_lib.strategies.legacy import MACrossoverStrategy
from trading_lib.strategies.bollinger import BollingerStrategy
from trading_lib.strategies.supertrend import SuperTrendStrategy
from trading_lib.strategies.registry import (
    StrategyRegistry,
    get_strategy,
    register_strategy,
    get_available_strategies,
    list_strategies,
)

# Регистрируем стратегии
register_strategy('ma_crossover', MACrossoverStrategy)
register_strategy('bollinger', BollingerStrategy)
register_strategy('supertrend', SuperTrendStrategy)

__all__ = [
    'BaseStrategy',
    'MACrossoverStrategy',
    'BollingerStrategy',
    'SuperTrendStrategy',
    'get_strategy',
    'register_strategy',
    'get_available_strategies',
    'list_strategies',
]
