"""
Ограничения на торговлю в зависимости от режима рынка.
"""

from typing import List
from trading_lib.regime.regimes import MarketRegime


STRATEGY_REGIME_RESTRICTIONS = {
    "ma_crossover": [
        MarketRegime.STRONG_UPTREND,
        MarketRegime.STRONG_DOWNTREND,
    ],
    "bollinger": [
        MarketRegime.RANGING,
    ],
    "supertrend": [
        MarketRegime.STRONG_UPTREND,
        MarketRegime.STRONG_DOWNTREND,
        MarketRegime.RANGING,
    ],
}


def is_strategy_allowed(strategy_name: str, regime: MarketRegime) -> bool:
    """Проверить, разрешена ли стратегия в данном режиме"""
    if regime == MarketRegime.HIGH_VOLATILITY:
        return False
    
    allowed_regimes = STRATEGY_REGIME_RESTRICTIONS.get(strategy_name, [])
    if not allowed_regimes:
        return regime == MarketRegime.RANGING
    
    return regime in allowed_regimes


def get_allowed_strategies(regime: MarketRegime) -> List[str]:
    """Получить список стратегий, разрешённых в данном режиме"""
    if regime == MarketRegime.HIGH_VOLATILITY:
        return []
    
    allowed = []
    for strategy, regimes in STRATEGY_REGIME_RESTRICTIONS.items():
        if regime in regimes:
            allowed.append(strategy)
    return allowed
