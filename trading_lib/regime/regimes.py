"""
Enum для режимов рынка.
"""

from enum import Enum


class MarketRegime(Enum):
    """Режимы рынка в порядке приоритета"""
    HIGH_VOLATILITY = "high_volatility"
    STRONG_UPTREND = "strong_uptrend"
    STRONG_DOWNTREND = "strong_downtrend"
    RANGING = "ranging"
    
    def __str__(self):
        return self.value
    
    @classmethod
    def from_string(cls, value: str):
        for regime in cls:
            if regime.value == value:
                return regime
        return cls.RANGING
