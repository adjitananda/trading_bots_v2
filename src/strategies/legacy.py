"""
Импортированные стратегии из старой системы.
Дата импорта: 2026-03-06
Оригинал: /home/trader/trading_bots_logs/strategies.py

Адаптировано для новой архитектуры.
"""

import pandas as pd
import pandas_ta as ta

from src.strategies.base import BaseStrategy


# ==================== СТРАТЕГИИ НА ОСНОВЕ СКОЛЬЗЯЩИХ СРЕДНИХ ====================


class MACrossoverStrategy(BaseStrategy):    """Стратегия кроссовера скользящих средних"""
    
    def get_signal(self, df):
        short_ma = self.params.get('short_ma', 14)
        long_ma = self.params.get('long_ma', 45)
        
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


class EMAStrategy(BaseStrategy):    """Стратегия на основе EMA"""
    
    def get_signal(self, df):
        ema_fast = self.params.get('ema_fast', 9)
        ema_slow = self.params.get('ema_slow', 21)
        
        df_copy = df.copy()
        df_copy[f'EMA_{ema_fast}'] = ta.ema(df_copy['close'], length=ema_fast)
        df_copy[f'EMA_{ema_slow}'] = ta.ema(df_copy['close'], length=ema_slow)
        
        if len(df_copy) < ema_slow or pd.isna(df_copy[f'EMA_{ema_fast}'].iloc[-1]):
            return 'none'
        
        ema_fast_current = df_copy[f'EMA_{ema_fast}'].iloc[-1]
        ema_fast_prev = df_copy[f'EMA_{ema_fast}'].iloc[-2]
        ema_slow_current = df_copy[f'EMA_{ema_slow}'].iloc[-1]
        ema_slow_prev = df_copy[f'EMA_{ema_slow}'].iloc[-2]
        
        if ema_fast_prev <= ema_slow_prev and ema_fast_current > ema_slow_current:
            return 'up'
        elif ema_fast_prev >= ema_slow_prev and ema_fast_current < ema_slow_current:
            return 'down'
        else:
            return 'none'


class TripleMAStrategy(BaseStrategy):    """Тройная стратегия скользящих средних (быстрая, средняя, медленная)"""
    
    def get_signal(self, df):
        fast = self.params.get('fast', 5)
        medium = self.params.get('medium', 13)
        slow = self.params.get('slow', 34)
        
        df_copy = df.copy()
        df_copy['SMA_FAST'] = ta.sma(df_copy['close'], length=fast)
        df_copy['SMA_MEDIUM'] = ta.sma(df_copy['close'], length=medium)
        df_copy['SMA_SLOW'] = ta.sma(df_copy['close'], length=slow)
        
        if len(df_copy) < slow:
            return 'none'
        
        # Быстрая MA выше средней и средней выше медленной = BUY
        fast_above_medium = df_copy['SMA_FAST'].iloc[-1] > df_copy['SMA_MEDIUM'].iloc[-1]
        medium_above_slow = df_copy['SMA_MEDIUM'].iloc[-1] > df_copy['SMA_SLOW'].iloc[-1]
        
        # Быстрая MA ниже средней и средней ниже медленной = SELL
        fast_below_medium = df_copy['SMA_FAST'].iloc[-1] < df_copy['SMA_MEDIUM'].iloc[-1]
        medium_below_slow = df_copy['SMA_MEDIUM'].iloc[-1] < df_copy['SMA_SLOW'].iloc[-1]
        
        if fast_above_medium and medium_above_slow:
            return 'up'
        elif fast_below_medium and medium_below_slow:
            return 'down'
        else:
            return 'none'

# ==================== СТРАТЕГИИ НА ОСНОВЕ ОСЦИЛЛЯТОРОВ ====================


class RSIOversoldStrategy(BaseStrategy):    """Стратегия по RSI (перекупленность/перепроданность)"""
    
    def get_signal(self, df):
        rsi_period = self.params.get('rsi_period', 14)
        oversold = self.params.get('oversold', 30)
        overbought = self.params.get('overbought', 70)
        
        df_copy = df.copy()
        df_copy['RSI'] = ta.rsi(df_copy['close'], length=rsi_period)
        
        if len(df_copy) < rsi_period or pd.isna(df_copy['RSI'].iloc[-1]):
            return 'none'
        
        rsi_current = df_copy['RSI'].iloc[-1]
        rsi_prev = df_copy['RSI'].iloc[-2]
        
        # Сигнал на покупку: RSI выходит из зоны перепроданности
        if rsi_prev <= oversold and rsi_current > oversold:
            return 'up'
        # Сигнал на продажу: RSI выходит из зоны перекупленности
        elif rsi_prev >= overbought and rsi_current < overbought:
            return 'down'
        else:
            return 'none'


class StochasticStrategy(BaseStrategy):    """Стратегия по стохастическому осциллятору"""
    
    def get_signal(self, df):
        k_period = self.params.get('k_period', 14)
        d_period = self.params.get('d_period', 3)
        oversold = self.params.get('oversold', 20)
        overbought = self.params.get('overbought', 80)
        
        df_copy = df.copy()
        stoch = ta.stoch(df_copy['high'], df_copy['low'], df_copy['close'], 
                         k=k_period, d=d_period)
        
        if stoch is None or len(df_copy) < k_period:
            return 'none'
        
        df_copy['STOCH_K'] = stoch[f'STOCHk_{k_period}_{d_period}_3']
        df_copy['STOCH_D'] = stoch[f'STOCHd_{k_period}_{d_period}_3']
        
        stoch_k_current = df_copy['STOCH_K'].iloc[-1]
        stoch_k_prev = df_copy['STOCH_K'].iloc[-2]
        
        # Сигнал на покупку: %K выходит из зоны перепроданности
        if stoch_k_prev <= oversold and stoch_k_current > oversold:
            return 'up'
        # Сигнал на продажу: %K выходит из зоны перекупленности
        elif stoch_k_prev >= overbought and stoch_k_current < overbought:
            return 'down'
        else:
            return 'none'

# ==================== КОМБИНИРОВАННЫЕ СТРАТЕГИИ ====================


class MACDStrategy(BaseStrategy):    """Стратегия по MACD"""
    
    def get_signal(self, df):
        fast = self.params.get('fast', 12)
        slow = self.params.get('slow', 26)
        signal = self.params.get('signal', 9)
        
        df_copy = df.copy()
        macd = ta.macd(df_copy['close'], fast=fast, slow=slow, signal=signal)
        
        if macd is None or len(df_copy) < slow:
            return 'none'
        
        df_copy['MACD'] = macd[f'MACD_{fast}_{slow}_{signal}']
        df_copy['MACD_SIGNAL'] = macd[f'MACDs_{fast}_{slow}_{signal}']
        df_copy['MACD_HIST'] = macd[f'MACDh_{fast}_{slow}_{signal}']
        
        macd_current = df_copy['MACD'].iloc[-1]
        macd_prev = df_copy['MACD'].iloc[-2]
        signal_current = df_copy['MACD_SIGNAL'].iloc[-1]
        signal_prev = df_copy['MACD_SIGNAL'].iloc[-2]
        
        if macd_prev <= signal_prev and macd_current > signal_current:
            return 'up'
        elif macd_prev >= signal_prev and macd_current < signal_current:
            return 'down'
        else:
            return 'none'


class MACDWithEMAStrategy(BaseStrategy):    """Комбинированная стратегия: MACD + EMA"""
    
    def get_signal(self, df):
        # Параметры MACD
        macd_fast = self.params.get('macd_fast', 12)
        macd_slow = self.params.get('macd_slow', 26)
        macd_signal = self.params.get('macd_signal', 9)
        
        # Параметры EMA
        ema_period = self.params.get('ema_period', 50)
        
        df_copy = df.copy()
        
        # Рассчитываем MACD
        macd = ta.macd(df_copy['close'], fast=macd_fast, slow=macd_slow, signal=macd_signal)
        if macd is None:
            return 'none'
        
        df_copy['MACD'] = macd[f'MACD_{macd_fast}_{macd_slow}_{macd_signal}']
        df_copy['MACD_SIGNAL'] = macd[f'MACDs_{macd_fast}_{macd_slow}_{macd_signal}']
        
        # Рассчитываем EMA
        df_copy['EMA'] = ta.ema(df_copy['close'], length=ema_period)
        
        if len(df_copy) < max(macd_slow, ema_period):
            return 'none'
        
        # Сигнал от MACD
        macd_signal_up = (df_copy['MACD'].iloc[-2] <= df_copy['MACD_SIGNAL'].iloc[-2] and 
                         df_copy['MACD'].iloc[-1] > df_copy['MACD_SIGNAL'].iloc[-1])
        macd_signal_down = (df_copy['MACD'].iloc[-2] >= df_copy['MACD_SIGNAL'].iloc[-2] and 
                           df_copy['MACD'].iloc[-1] < df_copy['MACD_SIGNAL'].iloc[-1])
        
        # Цена выше/ниже EMA
        price_above_ema = df_copy['close'].iloc[-1] > df_copy['EMA'].iloc[-1]
        
        # Комбинированные сигналы
        if macd_signal_up and price_above_ema:
            return 'up'
        elif macd_signal_down and not price_above_ema:
            return 'down'
        else:
            return 'none'


class RSIWithMAStrategy(BaseStrategy):    """Комбинированная стратегия: RSI + MA"""
    
    def get_signal(self, df):
        rsi_period = self.params.get('rsi_period', 14)
        oversold = self.params.get('oversold', 30)
        overbought = self.params.get('overbought', 70)
        ma_period = self.params.get('ma_period', 50)
        
        df_copy = df.copy()
        
        # RSI
        df_copy['RSI'] = ta.rsi(df_copy['close'], length=rsi_period)
        
        # Moving Average
        df_copy['MA'] = ta.sma(df_copy['close'], length=ma_period)
        
        if len(df_copy) < max(rsi_period, ma_period):
            return 'none'
        
        rsi_current = df_copy['RSI'].iloc[-1]
        rsi_prev = df_copy['RSI'].iloc[-2]
        price_current = df_copy['close'].iloc[-1]
        ma_current = df_copy['MA'].iloc[-1]
        
        # Сигнал на покупку: RSI выходит из перепроданности И цена выше MA
        if (rsi_prev <= oversold and rsi_current > oversold and 
            price_current > ma_current):
            return 'up'
        # Сигнал на продажу: RSI выходит из перекупленности И цена ниже MA
        elif (rsi_prev >= overbought and rsi_current < overbought and 
              price_current < ma_current):
            return 'down'
        else:
            return 'none'

# ==================== СТРАТЕГИИ НА ОСНОВЕ ВОЛАТИЛЬНОСТИ ====================


class BollingerBandsStrategy(BaseStrategy):    """Стратегия по полосам Боллинджера"""
    
    def get_signal(self, df):
        bb_period = self.params.get('bb_period', 20)
        bb_std = self.params.get('bb_std', 2)
        
        df_copy = df.copy()
        bbands = ta.bbands(df_copy['close'], length=bb_period, std=bb_std)
        
        if bbands is None or len(df_copy) < bb_period:
            return 'none'
        
        df_copy['BB_LOWER'] = bbands[f'BBL_{bb_period}_{bb_std}.0']
        df_copy['BB_UPPER'] = bbands[f'BBU_{bb_period}_{bb_std}.0']
        df_copy['BB_MIDDLE'] = bbands[f'BBM_{bb_period}_{bb_std}.0']
        
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


class ATRBreakoutStrategy(BaseStrategy):    """Стратегия пробоя на основе ATR"""
    
    def get_signal(self, df):
        atr_period = self.params.get('atr_period', 14)
        atr_multiplier = self.params.get('atr_multiplier', 1.5)
        lookback = self.params.get('lookback', 20)
        
        df_copy = df.copy()
        
        # Рассчитываем ATR
        df_copy['ATR'] = ta.atr(df_copy['high'], df_copy['low'], df_copy['close'], length=atr_period)
        
        if len(df_copy) < max(atr_period, lookback) or pd.isna(df_copy['ATR'].iloc[-1]):
            return 'none'
        
        # Находим максимум и минимум за последние N свечей
        highest_high = df_copy['high'].rolling(window=lookback).max().iloc[-1]
        lowest_low = df_copy['low'].rolling(window=lookback).min().iloc[-1]
        
        current_atr = df_copy['ATR'].iloc[-1]
        current_price = df_copy['close'].iloc[-1]
        
        # Уровни пробоя
        breakout_up = highest_high + (current_atr * atr_multiplier)
        breakout_down = lowest_low - (current_atr * atr_multiplier)
        
        if current_price >= breakout_up:
            return 'up'
        elif current_price <= breakout_down:
            return 'down'
        else:
            return 'none'

# ==================== ФАБРИКА СТРАТЕГИЙ ====================


# ==================== ФАБРИКА СТРАТЕГИЙ ====================

class StrategyFactory:
    """Фабрика для создания стратегий"""
    
    _strategies = {
        'm_a_crossover': MACrossoverStrategy,
        'e_m_a': EMAStrategy,
        'triple_m_a': TripleMAStrategy,
        'r_s_i_oversold': RSIOversoldStrategy,
        'stochastic': StochasticStrategy,
        'm_a_c_d': MACDStrategy,
        'm_a_c_d_with_e_m_a': MACDWithEMAStrategy,
        'r_s_i_with_m_a': RSIWithMAStrategy,
        'bollinger_bands': BollingerBandsStrategy,
        'a_t_r_breakout': ATRBreakoutStrategy,
    }
    
    @classmethod
    def create_strategy(cls, name: str, params: dict = None):
        """Создать стратегию по имени"""
        if name not in cls._strategies:
            available = ', '.join(cls._strategies.keys())
            raise ValueError(f"Unknown strategy: {name}. Available: {available}")
        
        strategy_class = cls._strategies[name]
        return strategy_class(params)
    
    @classmethod
    def get_all_strategies(cls):
        """Список всех доступных стратегий"""
        return list(cls._strategies.keys())
