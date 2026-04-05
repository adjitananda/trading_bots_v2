"""
Импортированные стратегии из старой системы.
Адаптировано для новой архитектуры с добавлением Bollinger и SuperTrend.
"""

import pandas as pd
import pandas_ta as ta

from trading_lib.strategies.base import BaseStrategy
from trading_lib.strategies.bollinger import BollingerStrategy
from trading_lib.strategies.supertrend import SuperTrendStrategy


# ==================== СТРАТЕГИИ НА ОСНОВЕ СКОЛЬЗЯЩИХ СРЕДНИХ ====================

class MACrossoverStrategy(BaseStrategy):
    """Стратегия кроссовера скользящих средних"""
    
    def __init__(self, params=None):
        super().__init__(params)
        self.short_ma = self.params.get('short_ma', 14)
        self.long_ma = self.params.get('long_ma', 45)
    
    def get_signal(self, df):
        short_ma = self.short_ma
        long_ma = self.long_ma
        
        df_copy = df.copy()
        df_copy[f'SMA_{short_ma}'] = ta.sma(df_copy['close'], length=short_ma)
        df_copy[f'SMA_{long_ma}'] = ta.sma(df_copy['close'], length=long_ma)
        
        if len(df_copy) < long_ma or pd.isna(df_copy[f'SMA_{short_ma}'].iloc[-1]):
            return 'none'
        
        short_ma_current = df_copy[f'SMA_{short_ma}'].iloc[-1]
        short_ma_prev = df_copy[f'SMA_{short_ma}'].iloc[-2]
        long_ma_current = df_copy[f'SMA_{long_ma}'].iloc[-1]
        long_ma_prev = df_copy[f'SMA_{long_ma}'].iloc[-2]
        
        if short_ma_prev <= long_ma_prev and short_ma_current > long_ma_current:
            return 'up'
        elif short_ma_prev >= long_ma_prev and short_ma_current < long_ma_current:
            return 'down'
        else:
            return 'none'


# ==================== СТРАТЕГИИ НА ОСНОВЕ ВОЛАТИЛЬНОСТИ ====================

class BollingerBandsStrategy(BaseStrategy):
    """Стратегия по полосам Боллинджера (оригинальная)"""
    
    def __init__(self, params=None):
        super().__init__(params)
        self.bb_period = self.params.get('bb_period', 20)
        self.bb_std = self.params.get('bb_std', 2)
    
    def get_signal(self, df):
        bb_period = self.bb_period
        bb_std = self.bb_std
        
        df_copy = df.copy()
        bbands = ta.bbands(df_copy['close'], length=bb_period, std=bb_std)
        
        if bbands is None or len(df_copy) < bb_period:
            return 'none'
        
        df_copy['BB_LOWER'] = bbands[f'BBL_{bb_period}_{bb_std}.0']
        df_copy['BB_UPPER'] = bbands[f'BBU_{bb_period}_{bb_std}.0']
        
        price_current = df_copy['close'].iloc[-1]
        price_prev = df_copy['close'].iloc[-2]
        bb_lower_current = df_copy['BB_LOWER'].iloc[-1]
        bb_upper_current = df_copy['BB_UPPER'].iloc[-1]
        
        # Сигнал на покупку: цена касается нижней полосы и отскакивает
        if price_prev <= bb_lower_current and price_current > bb_lower_current:
            return 'up'
        # Сигнал на продажу: цена касается верхней полосы и отскакивает
        elif price_prev >= bb_upper_current and price_current < bb_upper_current:
            return 'down'
        else:
            return 'none'


# ==================== ФАБРИКА СТРАТЕГИЙ ====================

class StrategyFactory:
    """Фабрика для создания стратегий"""
    
    _strategies = {
        # Основные стратегии
        'ma_crossover': MACrossoverStrategy,
        'bollinger': BollingerStrategy,      # Новая стратегия Bollinger
        'supertrend': SuperTrendStrategy,    # Новая стратегия SuperTrend
        # Legacy стратегии (для совместимости)
        'bollinger_bands': BollingerBandsStrategy,
        'ema': None,  # будет добавлена при необходимости
        'triple_ma': None,
        'rsi_oversold': None,
        'stochastic': None,
        'macd': None,
        'macd_with_ema': None,
        'rsi_with_ma': None,
        'atr_breakout': None,
    }
    
    @classmethod
    def create_strategy(cls, name: str, params: dict = None):
        """Создать стратегию по имени"""
        if name not in cls._strategies:
            available = ', '.join([k for k in cls._strategies.keys() if cls._strategies[k] is not None])
            raise ValueError(f"Unknown strategy: {name}. Available: {available}")
        
        strategy_class = cls._strategies[name]
        if strategy_class is None:
            raise ValueError(f"Strategy {name} is not fully implemented yet")
        
        return strategy_class(params)
    
    @classmethod
    def get_all_strategies(cls):
        """Список всех доступных стратегий"""
        return [k for k, v in cls._strategies.items() if v is not None]
