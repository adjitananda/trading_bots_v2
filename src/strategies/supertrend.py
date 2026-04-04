"""
SuperTrend стратегия.
Сигнал BUY когда цена пересекает SuperTrend снизу вверх.
Сигнал SELL когда цена пересекает SuperTrend сверху вниз.
"""

import pandas as pd
import pandas_ta as ta
from typing import Optional

from src.strategies.base import BaseStrategy


class SuperTrendStrategy(BaseStrategy):
    """Стратегия на основе SuperTrend"""
    
    def __init__(self, params: dict = None):
        super().__init__(params)
        self.atr_period = self.params.get('atr_period', 10)
        self.atr_multiplier = self.params.get('atr_multiplier', 3.0)
        self.tp_percent = self.params.get('take_profit', 4.0)
        self.sl_percent = self.params.get('stop_loss', 2.0)
    
    def get_signal(self, df: pd.DataFrame) -> str:
        """
        Возвращает торговый сигнал.
        
        Args:
            df: DataFrame с колонками ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            'up' - сигнал на покупку (пересечение снизу вверх)
            'down' - сигнал на продажу (пересечение сверху вниз)
            'none' - нет сигнала
        """
        if df is None or df.empty or len(df) < self.atr_period + 10:
            return 'none'
        
        df_copy = df.copy()
        
        # Рассчитываем SuperTrend
        supertrend = ta.supertrend(
            high=df_copy['high'],
            low=df_copy['low'],
            close=df_copy['close'],
            length=self.atr_period,
            multiplier=self.atr_multiplier
        )
        
        if supertrend is None or supertrend.empty:
            return 'none'
        
        # SuperTrend возвращает DataFrame с колонками 'SUPERT_*' и 'SUPERTd_*'
        # 'SUPERTd' показывает направление: 1 = восходящий, -1 = нисходящий
        
        trend_col = f'SUPERTd_{self.atr_period}_{self.atr_multiplier}.0'
        
        if trend_col not in supertrend.columns:
            return 'none'
        
        df_copy['TREND'] = supertrend[trend_col]
        
        if len(df_copy) < 2:
            return 'none'
        
        trend_current = df_copy['TREND'].iloc[-1]
        trend_prev = df_copy['TREND'].iloc[-2]
        
        # Пересечение снизу вверх: было -1, стало 1
        if trend_prev == -1 and trend_current == 1:
            return 'up'
        
        # Пересечение сверху вниз: было 1, стало -1
        if trend_prev == 1 and trend_current == -1:
            return 'down'
        
        return 'none'
    
    def get_tp_sl(self, entry_price: float, side: str) -> tuple:
        """
        Рассчитать цены тейк-профита и стоп-лосса.
        
        Args:
            entry_price: Цена входа
            side: 'BUY' или 'SELL'
        
        Returns:
            (take_profit_price, stop_loss_price)
        """
        if side.upper() == 'BUY':
            tp = entry_price * (1 + self.tp_percent / 100)
            sl = entry_price * (1 - self.sl_percent / 100)
        else:
            tp = entry_price * (1 - self.tp_percent / 100)
            sl = entry_price * (1 + self.sl_percent / 100)
        
        return tp, sl
    
    def get_info(self) -> dict:
        """Информация о стратегии"""
        return {
            'name': 'supertrend',
            'params': {
                'atr_period': self.atr_period,
                'atr_multiplier': self.atr_multiplier,
                'take_profit': self.tp_percent,
                'stop_loss': self.sl_percent
            }
        }
